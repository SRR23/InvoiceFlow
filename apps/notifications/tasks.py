"""
Celery tasks for sending emails and notifications.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


@shared_task
def send_invoice_email(invoice_id):
    """
    Send invoice email to client.
    """
    from apps.invoices.models import Invoice
    
    try:
        invoice = Invoice.objects.select_related('client', 'user').get(id=invoice_id)
        
        # Generate invoice link
        invoice_url = f"{settings.FRONTEND_URL}/invoice/{invoice.public_id}"
        
        # Email subject and content
        subject = f'Invoice {invoice.invoice_number} from {invoice.user.company_name or invoice.user.get_full_name()}'
        
        # TODO: Create email template
        html_message = f"""
        <h2>Invoice {invoice.invoice_number}</h2>
        <p>Dear {invoice.client.name},</p>
        <p>Please find your invoice attached below.</p>
        <p><a href="{invoice_url}">View Invoice</a></p>
        <p>Total Amount: {invoice.total_amount} {invoice.currency}</p>
        <p>Due Date: {invoice.due_date}</p>
        """
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.client.email] if invoice.client.email else [],
            html_message=html_message,
            fail_silently=False,
        )
        
        # Mark invoice as sent
        invoice.status = 'SENT'
        invoice.save(update_fields=['status'])
        
        return f"Invoice email sent to {invoice.client.email}"
    except Invoice.DoesNotExist:
        return f"Invoice {invoice_id} not found"


@shared_task
def send_payment_receipt(payment_id):
    """
    Send payment confirmation email.
    """
    from apps.payments.models import Payment
    
    try:
        payment = Payment.objects.select_related('invoice__client', 'invoice__user').get(id=payment_id)
        
        subject = f'Payment Confirmation - Invoice {payment.invoice.invoice_number}'
        
        html_message = f"""
        <h2>Payment Received</h2>
        <p>Dear {payment.invoice.client.name},</p>
        <p>We have received your payment of {payment.amount} {payment.currency}.</p>
        <p>Transaction ID: {payment.transaction_id}</p>
        <p>Invoice: {payment.invoice.invoice_number}</p>
        <p>Thank you for your payment!</p>
        """
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.invoice.client.email] if payment.invoice.client.email else [],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Payment receipt sent to {payment.invoice.client.email}"
    except Payment.DoesNotExist:
        return f"Payment {payment_id} not found"


@shared_task
def send_due_invoice_reminder():
    """
    Send reminder emails for due invoices.
    Runs daily via Celery Beat.
    """
    from apps.invoices.models import Invoice
    from django.utils import timezone
    
    today = timezone.now().date()
    
    # Find invoices due today or overdue
    due_invoices = Invoice.objects.filter(
        status__in=['SENT', 'DRAFT'],
        due_date__lte=today
    ).select_related('client', 'user')
    
    sent_count = 0
    for invoice in due_invoices:
        if invoice.client.email:
            invoice_url = f"{settings.FRONTEND_URL}/invoice/{invoice.public_id}"
            
            subject = f'Reminder: Invoice {invoice.invoice_number} is due'
            
            html_message = f"""
            <h2>Payment Reminder</h2>
            <p>Dear {invoice.client.name},</p>
            <p>This is a reminder that your invoice {invoice.invoice_number} is due.</p>
            <p>Amount: {invoice.total_amount} {invoice.currency}</p>
            <p>Due Date: {invoice.due_date}</p>
            <p><a href="{invoice_url}">Pay Now</a></p>
            """
            
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[invoice.client.email],
                html_message=html_message,
                fail_silently=True,
            )
            
            # Mark as overdue if past due date
            if invoice.due_date < today:
                invoice.status = 'OVERDUE'
                invoice.save(update_fields=['status'])
            
            sent_count += 1
    
    return f"Sent {sent_count} reminder emails"


@shared_task
def generate_invoice_pdf(invoice_id):
    """
    Generate PDF for an invoice.
    """
    from apps.invoices.models import Invoice
    # TODO: Implement PDF generation using reportlab or weasyprint
    # For now, this is a placeholder
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        # PDF generation logic here
        return f"PDF generated for invoice {invoice.invoice_number}"
    except Invoice.DoesNotExist:
        return f"Invoice {invoice_id} not found"
