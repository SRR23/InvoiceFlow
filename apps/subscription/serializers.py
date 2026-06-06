"""
Serializers for SaaS subscription API responses and request bodies.
"""

from rest_framework import serializers


class SubscriptionStatusSerializer(serializers.Serializer):
    """Current user's trial, Stripe subscription state, and app access flag."""

    trial_ends_at = serializers.DateTimeField(allow_null=True, read_only=True)
    subscription_status = serializers.CharField(read_only=True)
    has_active_app_access = serializers.BooleanField(read_only=True)


class SubscriptionCheckoutRequestSerializer(serializers.Serializer):
    """Optional body when starting Stripe Checkout for a subscription package."""

    package_code = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='Selects SubscriptionPackage.code; omit to use the default active package.',
    )


class SubscriptionCheckoutResponseSerializer(serializers.Serializer):
    """Stripe Checkout Session payload returned to the client."""

    checkout_url = serializers.URLField()
    session_id = serializers.CharField()
