"""
Serializers for Payment models.
"""
from rest_framework import serializers
from .models import Payment, WebhookEvent


class CreateGatewayPaymentRequestSerializer(serializers.Serializer):
    """Shared JSON body for starting a hosted checkout (Stripe or SSLCommerz)."""

    invoice_id = serializers.IntegerField(
        required=True,
        help_text="ID of the invoice to pay. Must belong to the authenticated business user.",
    )


class StripeCheckoutResponseSerializer(serializers.Serializer):
    """Successful Stripe Checkout session creation."""

    checkout_url = serializers.URLField(
        max_length=2048,
        help_text="Send the payer’s browser here to complete card payment on Stripe Checkout.",
    )
    invoice_id = serializers.IntegerField(help_text="Same invoice id as in the request.")


class SSLCommerzSessionResponseSerializer(serializers.Serializer):
    """Successful SSLCommerz hosted session creation."""

    redirect_url = serializers.URLField(
        max_length=2048,
        help_text="Send the payer’s browser here to complete payment on SSLCommerz.",
    )
    tran_id = serializers.CharField(
        help_text="Merchant transaction id (matches IPN / validation; format INV-<invoice_id>-<suffix>).",
    )
    session_key = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="SSLCommerz session key when returned by the gateway.",
    )
    invoice_id = serializers.IntegerField(help_text="Same invoice id as in the request.")


class PaymentErrorResponseSerializer(serializers.Serializer):
    """Standard error envelope for payment creation endpoints."""

    error = serializers.CharField(help_text="Human-readable error message.")


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
