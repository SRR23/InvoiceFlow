"""
Serializers for Payment models.
"""
from rest_framework import serializers
from .models import Payment, WebhookEvent


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = (
            'id', 'invoice', 'invoice_number', 'gateway', 'transaction_id',
            'amount', 'currency', 'status', 'paid_at', 'gateway_response',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for WebhookEvent model (mainly for admin/debugging)."""
    
    class Meta:
        model = WebhookEvent
        fields = (
            'id', 'gateway', 'event_type', 'payload', 'processed',
            'error_message', 'created_at', 'processed_at'
        )
        read_only_fields = ('id', 'created_at', 'processed_at')
