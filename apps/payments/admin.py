from django.contrib import admin
from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'invoice', 'gateway', 'amount', 'currency', 'status', 'paid_at', 'created_at')
    list_filter = ('gateway', 'status', 'created_at')
    search_fields = ('transaction_id', 'invoice__invoice_number', 'invoice__client__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('gateway', 'event_type', 'processed', 'created_at', 'processed_at')
    list_filter = ('gateway', 'event_type', 'processed', 'created_at')
    search_fields = ('event_type', 'payload')
    readonly_fields = ('created_at', 'processed_at')
