"""
Analytics models for tracking dashboard stats.
"""
from django.db import models
from django.conf import settings


class InvoiceAnalytics(models.Model):
    """
    Cached analytics data for a user.
    Can be recalculated periodically or on-demand.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analytics',
        help_text='The user these analytics belong to'
    )
    total_invoices = models.IntegerField(default=0, help_text='Total number of invoices')
    total_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Total revenue from paid invoices'
    )
    paid_invoices = models.IntegerField(default=0, help_text='Number of paid invoices')
    pending_invoices = models.IntegerField(default=0, help_text='Number of pending invoices')
    overdue_invoices = models.IntegerField(default=0, help_text='Number of overdue invoices')
    
    last_updated = models.DateTimeField(auto_now=True, help_text='When analytics were last calculated')
    
    class Meta:
        db_table = 'invoice_analytics'
        verbose_name = 'Invoice Analytics'
        verbose_name_plural = 'Invoice Analytics'
    
    def __str__(self):
        return f"Analytics for {self.user.email}"
