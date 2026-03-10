from django.contrib import admin
from .models import InvoiceAnalytics


@admin.register(InvoiceAnalytics)
class InvoiceAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_invoices', 'total_revenue', 'paid_invoices', 'pending_invoices', 'overdue_invoices', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('user__email',)
