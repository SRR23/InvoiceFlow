
import uuid
from django.db import models
from django.db.models import UniqueConstraint
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal


class Invoice(models.Model):
    """
    Invoice status choices.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invoices',
        help_text='The business user who owns this invoice'
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='invoices',
        help_text='The client this invoice is for'
    )
    invoice_number = models.CharField(
        max_length=50,
        db_index=True,
        help_text='Invoice number unique per user; assigned by the server on create',
    )
    issue_date = models.DateField(help_text='Date when invoice was issued')
    due_date = models.DateField(help_text='Date when invoice payment is due')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    
    # Financial fields
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='USD', help_text='ISO 4217 currency code')
    
    # Additional fields
    notes = models.TextField(blank=True, help_text='Additional notes or terms')
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        help_text='Public UUID for invoice link access'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'invoices'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-created_at']
        constraints = [
            UniqueConstraint(
                fields=('user', 'invoice_number'),
                name='invoices_user_invoice_number_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['public_id']),
            models.Index(fields=['invoice_number']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.client.name}"
    
    def calculate_totals(self):
        """Calculate subtotal, tax, and total_amount from invoice items."""
        items = self.items.all()
        self.subtotal = sum(item.total_price for item in items)
        self.tax = sum(item.total_price * (item.tax_rate / 100) for item in items)
        self.total_amount = self.subtotal + self.tax - self.discount
        self.save(update_fields=['subtotal', 'tax', 'total_amount'])


class InvoiceItem(models.Model):
    """
    Individual items within an invoice.
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items',
        help_text='The invoice this item belongs to'
    )
    title = models.CharField(max_length=255, help_text='Item title/name')
    description = models.TextField(blank=True, help_text='Item description')
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Item quantity'
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Price per unit'
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Tax rate percentage (e.g., 10.00 for 10%)'
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Total price (quantity × unit_price)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'invoice_items'
        verbose_name = 'Invoice Item'
        verbose_name_plural = 'Invoice Items'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.title} - {self.invoice.invoice_number}"
    
    def save(self, *args, **kwargs):
        """Calculate total_price before saving."""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        # Recalculate invoice totals
        self.invoice.calculate_totals()
