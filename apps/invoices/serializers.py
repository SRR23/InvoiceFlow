
from rest_framework import serializers
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
    
    class Meta:
        model = Invoice
        fields = (
            'id', 'client', 'client_name', 'client_email', 'invoice_number',
            'issue_date', 'due_date', 'status', 'subtotal', 'tax', 'discount',
            'total_amount', 'currency', 'notes', 'public_id', 'items',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'subtotal', 'tax', 'total_amount', 'public_id', 'created_at', 'updated_at')


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating invoices with items."""
    items = InvoiceItemSerializer(many=True)
    
    class Meta:
        model = Invoice
        fields = (
            'id', 'client', 'invoice_number', 'issue_date', 'due_date',
            'status', 'discount', 'currency', 'notes', 'items'
        )
        read_only_fields = ('id',)
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
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
