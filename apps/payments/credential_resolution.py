"""
Resolve Stripe / SSLCommerz credentials for a user.

Priority: merchant-specific ``MerchantGatewaySettings`` (non-empty secret fields),
then optional platform-wide defaults from Django settings (env) for development.
"""
from django.conf import settings

from apps.payments.models import MerchantGatewaySettings


def get_or_create_merchant_gateway_settings(user) -> MerchantGatewaySettings:
    """Return gateway settings row, creating it with a new webhook_public_id if needed."""
    gs, _ = MerchantGatewaySettings.objects.get_or_create(user=user)
    return gs


def resolve_stripe_secret_key(user) -> str:
    try:
        gs = user.merchant_gateway_settings
    except MerchantGatewaySettings.DoesNotExist:
        gs = None
    if gs and gs.get_stripe_secret_key():
        return gs.get_stripe_secret_key()
    return getattr(settings, "STRIPE_SECRET_KEY", "") or ""


def resolve_stripe_publishable_key(user) -> str:
    try:
        gs = user.merchant_gateway_settings
    except MerchantGatewaySettings.DoesNotExist:
        gs = None
    if gs and (gs.stripe_publishable_key or "").strip():
        return gs.stripe_publishable_key.strip()
    return getattr(settings, "STRIPE_PUBLIC_KEY", "") or ""


def resolve_stripe_webhook_secret(user) -> str:
    """Webhook signing secret for Stripe (per-merchant or platform default)."""
    try:
        gs = user.merchant_gateway_settings
    except MerchantGatewaySettings.DoesNotExist:
        gs = None
    if gs and gs.get_stripe_webhook_secret():
        return gs.get_stripe_webhook_secret()
    return getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or ""


def resolve_sslcommerz_credentials(user):
    """
    Returns (store_id, store_password, is_live).
    Falls back to platform settings when merchant fields are empty.
    """
    try:
        gs = user.merchant_gateway_settings
    except MerchantGatewaySettings.DoesNotExist:
        gs = None

    if gs and gs.sslcommerz_store_id and gs.get_sslcommerz_store_password():
        return (
            gs.sslcommerz_store_id.strip(),
            gs.get_sslcommerz_store_password(),
            gs.sslcommerz_is_live,
        )

    return (
        getattr(settings, "SSLCOMMERZ_STORE_ID", "") or "",
        getattr(settings, "SSLCOMMERZ_STORE_PASSWORD", "") or "",
        getattr(settings, "SSLCOMMERZ_IS_LIVE", False),
    )
