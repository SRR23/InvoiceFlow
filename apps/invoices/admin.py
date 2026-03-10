from django.contrib import admin
from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'client', 'user', 'status', 'total_amount', 'currency', 'due_date', 'created_at')
    list_filter = ('status', 'currency', 'created_at', 'due_date')
    search_fields = ('invoice_number', 'client__name', 'client__email', 'user__email')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    inlines = [InvoiceItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'client', 'invoice_number', 'public_id', 'status')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date')
        }),
        ('Financial', {
            'fields': ('subtotal', 'tax', 'discount', 'total_amount', 'currency')
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'invoice', 'quantity', 'unit_price', 'tax_rate', 'total_price')
    list_filter = ('created_at',)
    search_fields = ('title', 'invoice__invoice_number')
