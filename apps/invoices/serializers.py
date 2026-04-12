from django.db import transaction
from rest_framework import serializers

from apps.payments.payment_link_policy import is_invoice_past_due
from utils.constants import PAYMENT_STATUS_PENDING

from .invoice_numbers import allocate_next_invoice_number
from .models import Invoice, InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    """Serializer for InvoiceItem model."""
    
    class Meta:
        model = InvoiceItem
        fields = ('id', 'title', 'description', 'quantity', 'unit_price', 'tax_rate', 'total_price', 'created_at', 'updated_at')
        read_only_fields = ('id', 'total_price', 'created_at', 'updated_at')


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice model."""
    items = InvoiceItemSerializer(many=True, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)
    pending_payment_links = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            'id', 'client', 'client_name', 'client_email', 'invoice_number',
            'issue_date', 'due_date', 'status', 'subtotal', 'tax', 'discount',
            'total_amount', 'currency', 'notes', 'public_id', 'items',
            'pending_payment_links',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'invoice_number', 'subtotal', 'tax', 'total_amount',
            'public_id', 'pending_payment_links', 'created_at', 'updated_at',
        )

    def get_pending_payment_links(self, obj):
        """Hosted gateway URLs not yet completed (merchant can copy and send to the client)."""
        if is_invoice_past_due(obj):
            return []
        prefetched = getattr(obj, '_prefetched_pending_payment_links', None)
        if prefetched is not None:
            rows = prefetched[:25]
        else:
            rows = (
                obj.payments.filter(status=PAYMENT_STATUS_PENDING)
                .exclude(payment_url='')
                .order_by('-created_at')[:25]
            )
        due_iso = obj.due_date.isoformat() if obj.due_date else None
        return [
            {
                'id': p.id,
                'gateway': p.gateway,
                'payment_url': p.payment_url,
                'created_at': p.created_at,
                'valid_until': due_iso,
            }
            for p in rows
        ]


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating invoices with items."""
    items = InvoiceItemSerializer(many=True)
    
    class Meta:
        model = Invoice
        fields = (
            'id', 'client', 'invoice_number', 'issue_date', 'due_date',
            'status', 'discount', 'currency', 'notes', 'items',
        )
        read_only_fields = ('id', 'invoice_number')
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = validated_data['user']
        with transaction.atomic():
            validated_data['invoice_number'] = allocate_next_invoice_number(user)
            invoice = Invoice.objects.create(**validated_data)
            for item_data in items_data:
                InvoiceItem.objects.create(invoice=invoice, **item_data)
            invoice.calculate_totals()
        return invoice


class PublicInvoiceSerializer(serializers.ModelSerializer):
    """Serializer for public invoice view (no sensitive data)."""
    items = InvoiceItemSerializer(many=True, read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)
    business_name = serializers.CharField(source='user.company_name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = (
            'invoice_number', 'issue_date', 'due_date', 'status',
            'subtotal', 'tax', 'discount', 'total_amount', 'currency',
            'notes', 'client_name', 'client_email', 'business_name', 'items'
        )
