"""
Payment and WebhookEvent models.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal


class Payment(models.Model):
    """
    Payment gateway choices.
    """
    GATEWAY_CHOICES = [
        ('stripe', 'Stripe'),
        ('sslcommerz', 'SSLCommerz'),
    ]
    
    """
    Payment status choices.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    invoice = models.ForeignKey(
        'invoices.Invoice',
        on_delete=models.CASCADE,
        related_name='payments',
        help_text='The invoice this payment is for'
    )
    gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        help_text='Payment gateway used'
    )
    transaction_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Gateway transaction ID'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Payment amount'
    )
    currency = models.CharField(max_length=3, default='USD', help_text='ISO 4217 currency code')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    paid_at = models.DateTimeField(null=True, blank=True, help_text='When payment was completed')
    
    # Additional metadata
    gateway_response = models.JSONField(default=dict, blank=True, help_text='Raw gateway response')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice', '-created_at']),
            models.Index(fields=['gateway', 'status']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"{self.gateway} - {self.transaction_id} - {self.amount} {self.currency}"


class WebhookEvent(models.Model):
    """
    Webhook event log for payment gateways.
    Helps with debugging and tracking payment events.
    """
    GATEWAY_CHOICES = [
        ('stripe', 'Stripe'),
        ('sslcommerz', 'SSLCommerz'),
    ]
    
    gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        db_index=True,
        help_text='Payment gateway that sent the webhook'
    )
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text='Type of webhook event'
    )
    payload = models.JSONField(help_text='Raw webhook payload')
    processed = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether this event has been processed'
    )
    error_message = models.TextField(blank=True, help_text='Error message if processing failed')
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'webhook_events'
        verbose_name = 'Webhook Event'
        verbose_name_plural = 'Webhook Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gateway', '-created_at']),
            models.Index(fields=['event_type', 'processed']),
        ]
    
    def __str__(self):
        return f"{self.gateway} - {self.event_type} - {self.created_at}"
