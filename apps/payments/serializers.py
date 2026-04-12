"""
Serializers for Payment models.
"""
from django.urls import reverse
from rest_framework import serializers

from .models import MerchantGatewaySettings, Payment, WebhookEvent


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
    payment_id = serializers.IntegerField(
        help_text="Saved Payment row (pending) holding this checkout URL for sharing.",
    )


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
    payment_id = serializers.IntegerField(
        help_text="Saved Payment row (pending) holding this hosted URL for sharing.",
    )


class PaymentErrorResponseSerializer(serializers.Serializer):
    """Standard error envelope for payment creation endpoints."""

    error = serializers.CharField(help_text="Human-readable error message.")


class MerchantGatewaySettingsSerializer(serializers.ModelSerializer):
    """
    Read/update merchant-owned gateway credentials.

    Secrets are write-only; responses expose booleans and webhook URLs instead of raw secrets.
    """

    stripe_secret_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Stripe secret API key (sk_...). Omit on PATCH to leave unchanged; send empty string to clear.",
    )
    stripe_webhook_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Signing secret for the Stripe webhook endpoint (whsec_...).",
    )
    sslcommerz_store_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="SSLCommerz store password. Omit on PATCH to leave unchanged.",
    )

    stripe_secret_configured = serializers.SerializerMethodField(read_only=True)
    stripe_webhook_secret_configured = serializers.SerializerMethodField(read_only=True)
    sslcommerz_store_password_configured = serializers.SerializerMethodField(read_only=True)
    stripe_webhook_url = serializers.SerializerMethodField(read_only=True)
    sslcommerz_ipn_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MerchantGatewaySettings
        fields = (
            "webhook_public_id",
            "stripe_enabled",
            "stripe_publishable_key",
            "stripe_secret_key",
            "stripe_secret_configured",
            "stripe_webhook_secret",
            "stripe_webhook_secret_configured",
            "stripe_webhook_url",
            "sslcommerz_enabled",
            "sslcommerz_store_id",
            "sslcommerz_store_password",
            "sslcommerz_store_password_configured",
            "sslcommerz_is_live",
            "sslcommerz_ipn_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "webhook_public_id",
            "stripe_secret_configured",
            "stripe_webhook_secret_configured",
            "stripe_webhook_url",
            "sslcommerz_store_password_configured",
            "sslcommerz_ipn_url",
            "created_at",
            "updated_at",
        )

    def get_stripe_secret_configured(self, obj):
        return bool(obj.stripe_secret_key_encrypted)

    def get_stripe_webhook_secret_configured(self, obj):
        return bool(obj.stripe_webhook_secret_encrypted)

    def get_sslcommerz_store_password_configured(self, obj):
        return bool(obj.sslcommerz_store_password_encrypted)

    def get_stripe_webhook_url(self, obj):
        request = self.context.get("request")
        if not request:
            return ""
        path = reverse("payments:stripe-webhook-merchant", kwargs={"webhook_key": obj.webhook_public_id})
        return request.build_absolute_uri(path)

    def get_sslcommerz_ipn_url(self, obj):
        request = self.context.get("request")
        if not request:
            return ""
        path = reverse("payments:sslcommerz-webhook-merchant", kwargs={"webhook_key": obj.webhook_public_id})
        return request.build_absolute_uri(path)

    def update(self, instance, validated_data):
        stripe_secret = validated_data.pop("stripe_secret_key", None)
        stripe_wh = validated_data.pop("stripe_webhook_secret", None)
        ssl_pw = validated_data.pop("sslcommerz_store_password", None)

        instance = super().update(instance, validated_data)

        if stripe_secret is not None:
            if stripe_secret == "":
                instance.stripe_secret_key_encrypted = ""
            else:
                instance.set_stripe_secret_key(stripe_secret)
        if stripe_wh is not None:
            if stripe_wh == "":
                instance.stripe_webhook_secret_encrypted = ""
            else:
                instance.set_stripe_webhook_secret(stripe_wh)
        if ssl_pw is not None:
            if ssl_pw == "":
                instance.sslcommerz_store_password_encrypted = ""
            else:
                instance.set_sslcommerz_store_password(ssl_pw)

        instance.save()
        return instance


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = (
            'id', 'invoice', 'invoice_number', 'gateway', 'transaction_id',
            'amount', 'currency', 'status', 'paid_at', 'payment_url', 'gateway_response',
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
