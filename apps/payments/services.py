"""
Payment gateway services for Stripe and SSLCommerz.
"""
import logging
from decimal import Decimal

import requests
import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.invoices.models import Invoice
from apps.payments.models import Payment
from utils.constants import (
    INVOICE_STATUS_PAID,
    PAYMENT_GATEWAY_SSLCOMMERZ,
    PAYMENT_GATEWAY_STRIPE,
    PAYMENT_STATUS_COMPLETED,
)

logger = logging.getLogger(__name__)


def _stripe_event_to_dict(event):
    """Serialize a Stripe Event to a plain dict for JSONField storage."""
    try:
        from stripe.util import convert_to_dict

        return convert_to_dict(event)
    except Exception:
        if hasattr(event, "to_dict"):
            return event.to_dict()
        return dict(event)


class PaymentGatewayMixin:
    """Shared helpers for recording gateway success and receipts."""

    @staticmethod
    def webhook_event_already_processed_stripe(stripe_event_id, current_webhook_pk):
        """True if another row already recorded this Stripe event as processed."""
        from apps.payments.models import WebhookEvent

        qs = WebhookEvent.objects.filter(
            gateway=PAYMENT_GATEWAY_STRIPE,
            payload__id=stripe_event_id,
            processed=True,
        )
        if current_webhook_pk:
            qs = qs.exclude(pk=current_webhook_pk)
        return qs.exists()

    @staticmethod
    @transaction.atomic
    def finalize_successful_payment(invoice, gateway, transaction_id, amount, currency, gateway_response):
        """
        Idempotently mark invoice paid and upsert a completed Payment row.

        Returns True when the invoice was not PAID before this call and is now PAID
        (caller may send receipt). Duplicate webhooks return False.
        """
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        was_unpaid = locked.status != INVOICE_STATUS_PAID

        payment, created = Payment.objects.get_or_create(
            transaction_id=transaction_id,
            defaults={
                "invoice": locked,
                "gateway": gateway,
                "amount": amount,
                "currency": currency,
                "status": PAYMENT_STATUS_COMPLETED,
                "paid_at": timezone.now(),
                "gateway_response": gateway_response or {},
            },
        )

        if payment.invoice_id != locked.id:
            raise ValueError("Transaction ID is already associated with a different invoice")

        if not created:
            payment.status = PAYMENT_STATUS_COMPLETED
            payment.paid_at = timezone.now()
            payment.gateway_response = gateway_response or {}
            payment.amount = amount
            payment.currency = currency
            payment.save()

        if was_unpaid:
            locked.status = INVOICE_STATUS_PAID
            locked.save(update_fields=["status"])
            return True
        return False

    @staticmethod
    def send_receipt_async(invoice_id, transaction_id_for_log):
        """Queue payment receipt email after successful charge (best-effort)."""
        try:
            payment = Payment.objects.filter(
                invoice_id=invoice_id,
                transaction_id=transaction_id_for_log,
            ).first()
            if not payment:
                return
            from apps.notifications.tasks import send_payment_receipt

            send_payment_receipt.delay(payment.id)
        except Exception as exc:
            logger.warning("Could not queue payment receipt: %s", exc)


class StripeService:
    """Service for handling Stripe payments."""

    # Checkout Session events that indicate a successful payment for our integration.
    _CHECKOUT_SUCCESS_TYPES = frozenset(
        {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
        }
    )

    @staticmethod
    def create_checkout_session(invoice):
        """
        Create a Stripe checkout session for an invoice.
        Returns the checkout URL.
        """

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": invoice.currency.lower(),
                            "product_data": {
                                "name": f"Invoice {invoice.invoice_number}",
                            },
                            "unit_amount": int(invoice.total_amount * 100),  # Convert to cents
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
                metadata={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                },
            )

            return checkout_session.url
        except Exception as e:
            # Log error
            raise Exception(f"Stripe checkout session creation failed: {str(e)}") from e

    @staticmethod
    def process_webhook(webhook_event):
        """
        Process a Stripe webhook event stored on ``WebhookEvent`` (payload = full Stripe event dict).
        Updates invoice and payment status for successful Checkout sessions.
        """
        payload = webhook_event.payload
        event_type = payload.get("type")
        event_id = payload.get("id")

        if not event_id:
            raise ValueError("Stripe event missing id")

        # Idempotency: another worker may have already processed this Stripe event id.
        prior_done = PaymentGatewayMixin.webhook_event_already_processed_stripe(
            event_id, webhook_event.pk
        )
        if prior_done:
            logger.info("Skipping already-processed Stripe event %s", event_id)
            return

        if event_type in StripeService._CHECKOUT_SUCCESS_TYPES:
            session = payload.get("data", {}).get("object") or {}
            StripeService._handle_checkout_session_success(session)
            return

        # Other event types are acknowledged without action (subscription, etc.).
        logger.debug("Stripe webhook type %s ignored (no handler)", event_type)

    @staticmethod
    def _handle_checkout_session_success(session):
        """Apply a paid Checkout Session to the invoice referenced in metadata."""
        metadata = session.get("metadata") or {}
        invoice_id_raw = metadata.get("invoice_id")
        if not invoice_id_raw:
            raise ValueError("checkout.session missing metadata.invoice_id")

        try:
            invoice_id = int(invoice_id_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid metadata.invoice_id") from exc

        payment_status = (session.get("payment_status") or "").lower()
        if payment_status != "paid":
            logger.info(
                "Checkout session %s payment_status=%s — skipping mark paid",
                session.get("id"),
                payment_status,
            )
            return

        session_id = session.get("id")
        if not session_id:
            raise ValueError("checkout.session missing id")

        amount_total = session.get("amount_total")
        currency = (session.get("currency") or "usd").upper()

        invoice = Invoice.objects.filter(pk=invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice id={invoice_id} not found")

        if invoice.currency.upper() != currency:
            raise ValueError(
                f"Currency mismatch: invoice {invoice.currency} vs session {currency}"
            )

        # amount_total is in smallest currency unit (e.g. cents).
        if amount_total is None:
            raise ValueError("checkout.session missing amount_total")
        paid_decimal = Decimal(amount_total) / Decimal(100)
        if abs(paid_decimal - invoice.total_amount) > Decimal("0.01"):
            raise ValueError(
                f"Amount mismatch: invoice {invoice.total_amount} vs session {paid_decimal}"
            )

        receipt_send = PaymentGatewayMixin.finalize_successful_payment(
            invoice=invoice,
            gateway=PAYMENT_GATEWAY_STRIPE,
            transaction_id=session_id,
            amount=paid_decimal,
            currency=currency,
            gateway_response=session,
        )
        if receipt_send:
            PaymentGatewayMixin.send_receipt_async(invoice.id, session_id)


class SSLCommerzService:
    """Service for handling SSLCommerz payments."""

    @staticmethod
    def _api_base():
        if settings.SSLCOMMERZ_IS_LIVE:
            return "https://securepay.sslcommerz.com"
        return "https://sandbox.sslcommerz.com"

    @staticmethod
    def create_payment_session(invoice):
        """
        Create an SSLCommerz payment session for an invoice.
        Returns payment data including redirect URL.
        """

        store_id = settings.SSLCOMMERZ_STORE_ID
        store_password = settings.SSLCOMMERZ_STORE_PASSWORD
        is_live = settings.SSLCOMMERZ_IS_LIVE

        # Determine API URL based on live/sandbox mode
        if is_live:
            api_url = "https://securepay.sslcommerz.com"
        else:
            api_url = "https://sandbox.sslcommerz.com"

        # Prepare payment data
        payment_data = {
            "store_id": store_id,
            "store_passwd": store_password,
            "total_amount": str(invoice.total_amount),
            "currency": invoice.currency,
            "tran_id": f"INV-{invoice.id}-{invoice.public_id.hex[:8]}",
            "success_url": f"{settings.FRONTEND_URL}/payment/success",
            "fail_url": f"{settings.FRONTEND_URL}/payment/fail",
            "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel",
            "emi_option": 0,
            "cus_name": invoice.client.name,
            "cus_email": invoice.client.email or "",
            "cus_phone": invoice.client.phone or "",
            "product_name": f"Invoice {invoice.invoice_number}",
            "product_category": "Invoice",
            "product_profile": "general",
        }

        try:
            response = requests.post(
                f"{api_url}/gwprocess/v4/api.php",
                data=payment_data,
                timeout=60,
            )

            if response.status_code == 200:
                # Parse response
                # SSLCommerz returns form data or JSON
                return {
                    "redirect_url": response.url if hasattr(response, "url") else None,
                    "payment_data": payment_data,
                }
            else:
                raise Exception(f"SSLCommerz API error: {response.status_code}")
        except Exception as e:
            raise Exception(f"SSLCommerz payment session creation failed: {str(e)}") from e

    @staticmethod
    def validate_transaction(val_id):
        """
        Call SSLCommerz validation API to confirm ``val_id`` after IPN.
        Returns the parsed validation payload (dict).
        """
        if not val_id:
            raise ValueError("val_id is required")
        base = SSLCommerzService._api_base()
        url = f"{base}/validator/api/validationserverAPI.php"
        params = {
            "val_id": val_id,
            "store_id": settings.SSLCOMMERZ_STORE_ID,
            "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
            "format": "json",
            "v": "1",
        }
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            raise ValueError("Unexpected validation response shape")

        status = (data.get("status") or "").strip().upper()
        if status != "VALID":
            raise ValueError(f"SSLCommerz validation status is not VALID: {status!r}")

        return data

    @staticmethod
    def parse_invoice_id_from_tran_id(tran_id):
        """
        Parse invoice PK from our ``tran_id`` format: INV-<id>-<suffix>.
        """
        if not tran_id:
            return None
        parts = str(tran_id).split("-")
        if len(parts) < 3 or parts[0].upper() != "INV":
            return None
        try:
            return int(parts[1])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def process_ipn(webhook_event):
        """
        Process an SSLCommerz IPN (Instant Payment Notification).
        Verifies ``val_id`` server-side, then updates invoice and payment status.
        """
        payload = webhook_event.payload
        if not isinstance(payload, dict):
            raise ValueError("IPN payload must be a dict")

        val_id = payload.get("val_id") or payload.get("valId")
        tran_id = payload.get("tran_id") or payload.get("tranId")

        if not val_id:
            raise ValueError("IPN missing val_id")

        # Idempotency: same val_id already completed.
        if Payment.objects.filter(
            gateway=PAYMENT_GATEWAY_SSLCOMMERZ,
            transaction_id=val_id,
            status=PAYMENT_STATUS_COMPLETED,
        ).exists():
            logger.info("SSLCommerz IPN duplicate for val_id=%s — skipping", val_id)
            return

        validated = SSLCommerzService.validate_transaction(val_id)

        validated_tran = validated.get("tran_id") or tran_id
        if tran_id and validated_tran and str(validated_tran) != str(tran_id):
            raise ValueError("tran_id mismatch between IPN and validation response")

        invoice_id = SSLCommerzService.parse_invoice_id_from_tran_id(validated_tran)
        if not invoice_id:
            raise ValueError(f"Could not parse invoice from tran_id={validated_tran!r}")

        invoice = Invoice.objects.filter(pk=invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice id={invoice_id} not found")

        amount_raw = (
            validated.get("amount")
            or validated.get("store_amount")
            or validated.get("currency_amount")
        )
        if amount_raw is None:
            raise ValueError("Validation response missing amount")
        paid_decimal = Decimal(str(amount_raw))
        currency = (validated.get("currency") or invoice.currency or "BDT").upper()

        if invoice.currency.upper() != currency:
            raise ValueError(
                f"Currency mismatch: invoice {invoice.currency} vs gateway {currency}"
            )

        if abs(paid_decimal - invoice.total_amount) > Decimal("0.01"):
            raise ValueError(
                f"Amount mismatch: invoice {invoice.total_amount} vs gateway {paid_decimal}"
            )

        receipt_send = PaymentGatewayMixin.finalize_successful_payment(
            invoice=invoice,
            gateway=PAYMENT_GATEWAY_SSLCOMMERZ,
            transaction_id=val_id,
            amount=paid_decimal,
            currency=currency,
            gateway_response={"ipn": payload, "validated": validated},
        )
        if receipt_send:
            PaymentGatewayMixin.send_receipt_async(invoice.id, val_id)


# Export for Stripe webhook view
stripe_event_to_dict = _stripe_event_to_dict
