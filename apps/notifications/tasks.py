"""
Celery tasks for sending emails and notifications.
"""
import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from utils.constants import PAYMENT_STATUS_PENDING
from utils.invoice_pdf import build_invoice_pdf_bytes

logger = logging.getLogger(__name__)

# Display label for Invoice.status == "SENT" (must match Invoice.STATUS_CHOICES).
_INVOICE_SENT_STATUS_LABEL = "Sent"


def _pending_payment_links_for_invoice(invoice_id: int):
    """
    Hosted gateway URLs saved for this invoice (for email body).

    Queries ``Payment`` by ``invoice_id`` so results do not depend on reverse-manager
    caching or prefetch state on an ``Invoice`` instance.
    """
    from apps.payments.models import Payment

    qs = (
        Payment.objects.filter(invoice_id=invoice_id, status=PAYMENT_STATUS_PENDING)
        .exclude(payment_url="")
        .order_by("-created_at")
    )
    out = []
    for p in qs:
        url = (p.payment_url or "").strip()
        if not url:
            continue
        out.append({"gateway_label": p.get_gateway_display(), "url": url})
    # Help debug “no links in email” when pending rows exist but URLs were never stored.
    if not out:
        pending_no_url = Payment.objects.filter(
            invoice_id=invoice_id, status=PAYMENT_STATUS_PENDING
        ).filter(Q(payment_url="") | Q(payment_url__isnull=True)).count()
        if pending_no_url:
            logger.warning(
                "send_invoice_email: invoice %s has %s pending payment(s) with no "
                "payment_url; generate Stripe/SSL links before sending, or URLs were cleared.",
                invoice_id,
                pending_no_url,
            )
    return out


def _merchant_name(user):
    name = (getattr(user, "company_name", "") or "").strip()
    return name or user.get_full_name() or user.email


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def send_invoice_email(invoice_id):
    """
    Send invoice email to client with HTML template and PDF attachment.
    """
    from apps.invoices.models import Invoice

    try:
        invoice = (
            Invoice.objects.select_related("client", "user")
            .prefetch_related("items")
            .get(id=invoice_id)
        )

        if not invoice.client.email:
            logger.warning(
                "send_invoice_email: invoice %s has no client email; skipping",
                invoice_id,
            )
            return "Skipped: no client email"

        # Mark sent before PDF/email body so the attachment and copy reflect "Sent".
        invoice.status = "SENT"
        invoice.save(update_fields=["status"])
        invoice.refresh_from_db(fields=["status"])

        merchant_name = _merchant_name(invoice.user)
        invoice_url = f"{settings.FRONTEND_URL}/invoice/p/{invoice.public_id}"
        payment_links = _pending_payment_links_for_invoice(invoice_id)
        logger.info(
            "send_invoice_email: invoice=%s status=%s payment_links=%s",
            invoice_id,
            invoice.status,
            len(payment_links),
        )
        context = {
            "merchant_name": merchant_name,
            "client_name": invoice.client.name,
            "invoice_number": invoice.invoice_number,
            "invoice_url": invoice_url,
            "total_amount": invoice.total_amount,
            "currency": invoice.currency,
            "due_date": invoice.due_date,
            "issue_date": invoice.issue_date,
            "payment_links": payment_links,
        }

        subject = f"Invoice {invoice.invoice_number} from {merchant_name}"
        html_body = render_to_string("emails/invoice_email.html", context)
        text_body = render_to_string("emails/invoice_email.txt", context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invoice.client.email],
        )
        email.attach_alternative(html_body, "text/html")

        try:
            pdf_bytes = build_invoice_pdf_bytes(
                invoice,
                status_display=_INVOICE_SENT_STATUS_LABEL,
            )
            safe_name = "".join(
                c for c in invoice.invoice_number if c.isalnum() or c in "-_"
            )[:60] or str(invoice.id)
            email.attach(
                f"invoice-{safe_name}.pdf",
                pdf_bytes,
                "application/pdf",
            )
        except Exception as exc:
            logger.warning(
                "send_invoice_email: could not attach PDF for invoice %s: %s",
                invoice_id,
                exc,
            )

        email.send(fail_silently=False)

        return f"Invoice email sent to {invoice.client.email}"
    except Invoice.DoesNotExist:
        logger.warning("send_invoice_email: invoice %s not found", invoice_id)
        return f"Invoice {invoice_id} not found"


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def send_payment_receipt(payment_id):
    """
    Send payment confirmation email.
    """
    from apps.payments.models import Payment

    try:
        payment = Payment.objects.select_related("invoice__client", "invoice__user").get(
            id=payment_id
        )

        if not payment.invoice.client.email:
            logger.warning(
                "send_payment_receipt: payment %s client has no email; skipping",
                payment_id,
            )
            return "Skipped: no client email"

        inv = payment.invoice
        merchant_name = _merchant_name(inv.user)
        context = {
            "merchant_name": merchant_name,
            "client_name": inv.client.name,
            "invoice_number": inv.invoice_number,
            "amount": payment.amount,
            "currency": payment.currency,
            "transaction_id": payment.transaction_id,
        }

        subject = f"Payment Confirmation - Invoice {inv.invoice_number}"
        html_body = render_to_string("emails/payment_receipt.html", context)
        text_body = render_to_string("emails/payment_receipt.txt", context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[inv.client.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)

        return f"Payment receipt sent to {inv.client.email}"
    except Payment.DoesNotExist:
        logger.warning("send_payment_receipt: payment %s not found", payment_id)
        return f"Payment {payment_id} not found"


@shared_task
def send_due_invoice_reminder():
    """
    Send reminder emails for due invoices.
    Runs daily via Celery Beat.
    """
    from apps.invoices.models import Invoice

    today = timezone.now().date()

    due_invoices = Invoice.objects.filter(
        status__in=["SENT", "DRAFT"],
        due_date__lte=today,
    ).select_related("client", "user")

    sent_count = 0
    for invoice in due_invoices:
        if not invoice.client.email:
            continue

        merchant_name = _merchant_name(invoice.user)
        invoice_url = f"{settings.FRONTEND_URL}/invoice/p/{invoice.public_id}"
        is_overdue = invoice.due_date < today

        context = {
            "merchant_name": merchant_name,
            "client_name": invoice.client.name,
            "invoice_number": invoice.invoice_number,
            "total_amount": invoice.total_amount,
            "currency": invoice.currency,
            "due_date": invoice.due_date,
            "invoice_url": invoice_url,
            "is_overdue": is_overdue,
        }

        subject = f"Reminder: Invoice {invoice.invoice_number} is due"
        html_body = render_to_string("emails/due_reminder.html", context)
        text_body = render_to_string("emails/due_reminder.txt", context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invoice.client.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=True)

        if is_overdue:
            invoice.status = "OVERDUE"
            invoice.save(update_fields=["status"])

        sent_count += 1

    return f"Sent {sent_count} reminder emails"


@shared_task
def generate_invoice_pdf(invoice_id):
    """
    Generate a PDF file for an invoice and save it under MEDIA_ROOT/invoices/pdf/.
    """
    from apps.invoices.models import Invoice

    try:
        invoice = (
            Invoice.objects.select_related("client", "user")
            .prefetch_related("items")
            .get(id=invoice_id)
        )
    except Invoice.DoesNotExist:
        logger.warning("generate_invoice_pdf: invoice %s not found", invoice_id)
        return f"Invoice {invoice_id} not found"

    pdf_bytes = build_invoice_pdf_bytes(invoice)
    out_dir = Path(settings.MEDIA_ROOT) / "invoices" / "pdf"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_num = "".join(
        c for c in invoice.invoice_number if c.isalnum() or c in "-_"
    )[:80] or str(invoice.id)
    filename = f"invoice-{invoice.id}-{safe_num}.pdf"
    path = out_dir / filename
    path.write_bytes(pdf_bytes)

    rel = f"invoices/pdf/{filename}"
    logger.info("generate_invoice_pdf: wrote %s", path)
    return f"PDF saved: {rel} ({path})"
