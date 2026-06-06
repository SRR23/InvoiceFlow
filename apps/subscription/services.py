"""
Platform Stripe subscription (SaaS) — Checkout + webhook sync.

Checkout uses **dynamic** ``price_data`` (no stored Stripe ``price_xxx``). Amounts come from
``SubscriptionPackage`` (active row, or the row matching ``package_code``).

Uses ``settings.STRIPE_SECRET_KEY``. Webhook events must hit the **platform** Stripe webhook URL
(``/api/payments/webhooks/stripe/`` with ``STRIPE_WEBHOOK_SECRET``) for the same Stripe account.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import stripe
from django.conf import settings

from apps.accounts.models import User
from utils.constants import (
    SAAS_SUBSCRIPTION_CHECKOUT_PURPOSE,
    SUBSCRIPTION_STATUS_CANCELED,
    SUBSCRIPTION_STATUS_NONE,
)

logger = logging.getLogger(__name__)


def _set_stripe_platform_key() -> None:
    key = (getattr(settings, 'STRIPE_SECRET_KEY', '') or '').strip()
    if not key:
        raise ValueError(
            'STRIPE_SECRET_KEY is not configured. Set it for platform SaaS billing.'
        )
    stripe.api_key = key


def _billing_cycle_to_stripe_interval(billing_cycle: str) -> str:
    """Map ``SubscriptionPackage.billing_cycle`` to Stripe ``recurring.interval``."""
    raw = (billing_cycle or 'monthly').strip().lower()
    if raw in ('yearly', 'annual', 'year', 'yr'):
        return 'year'
    if raw in ('monthly', 'month', 'mo', ''):
        return 'month'
    if raw in ('weekly', 'week', 'wk'):
        return 'week'
    if raw in ('daily', 'day'):
        return 'day'
    logger.warning('Unknown billing_cycle %r; defaulting to month', billing_cycle)
    return 'month'


def _load_subscription_package(package_code: str | None):
    """Return an active ``SubscriptionPackage`` instance."""
    try:
        from .models import SubscriptionPackage
    except Exception as exc:  # pragma: no cover - misconfigured app
        raise ValueError(
            'Subscription packages are not available (import error). '
            'Fix the subscription app configuration.'
        ) from exc

    qs = SubscriptionPackage.objects.filter(is_active=True)
    if package_code:
        pkg = qs.filter(code=str(package_code).strip()).first()
        if not pkg:
            raise ValueError(f'Unknown or inactive subscription package code: {package_code!r}')
        return pkg

    pkg = qs.order_by('id').first()
    if not pkg:
        raise ValueError(
            'No active SubscriptionPackage found. Add at least one active package in the database.'
        )
    return pkg


def _subscription_line_item_from_package(pkg) -> dict[str, Any]:
    """Build a Checkout ``line_items`` entry using ``price_data`` (no Stripe Price id)."""
    currency = (pkg.currency or 'usd').strip().lower()
    if len(currency) != 3:
        raise ValueError('Package currency must be a 3-letter ISO 4217 code.')

    unit_amount = int(
        (Decimal(str(pkg.price)) * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    )
    if unit_amount < 1:
        raise ValueError('Package price must be greater than zero.')

    interval = _billing_cycle_to_stripe_interval(pkg.billing_cycle)
    product_name = (pkg.name or 'Subscription').strip()[:120] or 'Subscription'

    return {
        'price_data': {
            'currency': currency,
            'unit_amount': unit_amount,
            'recurring': {'interval': interval},
            'product_data': {'name': product_name},
        },
        'quantity': 1,
    }


def create_subscription_checkout_session(
    user: User,
    *,
    package_code: str | None = None,
) -> dict[str, str]:
    """
    Create a Stripe Checkout Session in ``subscription`` mode using dynamic ``price_data``.

    ``package_code`` selects ``SubscriptionPackage``; if omitted, the first active package (by id) is used.

    Returns ``checkout_url`` and ``session_id``.
    """
    pkg = _load_subscription_package(package_code)
    line_item = _subscription_line_item_from_package(pkg)

    _set_stripe_platform_key()

    success_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/payment/success"
        "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{settings.FRONTEND_URL.rstrip('/')}/payment/cancel"

    params: dict[str, Any] = {
        'mode': 'subscription',
        'line_items': [line_item],
        'success_url': success_url,
        'cancel_url': cancel_url,
        'client_reference_id': str(user.id),
        'metadata': {
            'user_id': str(user.id),
            'checkout_purpose': SAAS_SUBSCRIPTION_CHECKOUT_PURPOSE,
            'package_code': pkg.code,
        },
        'subscription_data': {
            'metadata': {
                'user_id': str(user.id),
                'checkout_purpose': SAAS_SUBSCRIPTION_CHECKOUT_PURPOSE,
                'package_code': pkg.code,
            },
        },
    }
    cust = (user.stripe_customer_id or '').strip()
    if cust:
        params['customer'] = cust
    else:
        params['customer_email'] = user.email

    session = stripe.checkout.Session.create(**params)
    return {'checkout_url': session.url, 'session_id': session.id}


def apply_subscription_checkout_completed(session: dict) -> None:
    """
    After a successful subscription Checkout Session, attach Stripe ids and status on User.

    Expects ``metadata.checkout_purpose`` == saas_subscription and ``metadata.user_id``.
    """
    if (session.get('mode') or '').lower() != 'subscription':
        raise ValueError('Expected subscription mode checkout session')

    metadata = session.get('metadata') or {}
    if metadata.get('checkout_purpose') != SAAS_SUBSCRIPTION_CHECKOUT_PURPOSE:
        raise ValueError('checkout.session is not a SaaS subscription checkout')

    user_id_raw = metadata.get('user_id')
    if not user_id_raw:
        raise ValueError('SaaS subscription checkout missing metadata.user_id')
    user_id = int(user_id_raw)

    payment_status = (session.get('payment_status') or '').lower()
    if payment_status not in ('paid', 'no_payment_required'):
        logger.info(
            'Skipping SaaS subscription checkout session %s payment_status=%s',
            session.get('id'),
            payment_status,
        )
        return

    customer_id = (session.get('customer') or '').strip()
    subscription_id = (session.get('subscription') or '').strip()
    if not subscription_id:
        raise ValueError('Subscription checkout missing subscription id')

    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise ValueError(f'User id={user_id} not found for SaaS subscription')

    _set_stripe_platform_key()
    sub = stripe.Subscription.retrieve(subscription_id)
    raw_status = (sub.get('status') or '').lower() or SUBSCRIPTION_STATUS_NONE

    user.stripe_customer_id = customer_id or user.stripe_customer_id
    user.stripe_subscription_id = subscription_id
    user.subscription_status = raw_status
    user.save(update_fields=['stripe_customer_id', 'stripe_subscription_id', 'subscription_status'])


def sync_subscription_from_stripe_payload(subscription_object: dict) -> None:
    """Update ``User.subscription_status`` from a Stripe Subscription object (webhook)."""
    sub_id = (subscription_object.get('id') or '').strip()
    if not sub_id:
        return
    user = User.objects.filter(stripe_subscription_id=sub_id).first()
    if not user:
        logger.warning('Stripe subscription %s: no matching user', sub_id)
        return
    raw_status = (subscription_object.get('status') or '').lower() or SUBSCRIPTION_STATUS_NONE
    if user.subscription_status == raw_status:
        return
    user.subscription_status = raw_status
    user.save(update_fields=['subscription_status'])


def mark_subscription_deleted(subscription_object: dict) -> None:
    """Stripe ended the subscription — revoke paid access (no self-serve cancel in-app)."""
    sub_id = (subscription_object.get('id') or '').strip()
    if not sub_id:
        return
    updated = User.objects.filter(stripe_subscription_id=sub_id).update(
        subscription_status=SUBSCRIPTION_STATUS_CANCELED
    )
    if not updated:
        logger.warning('Stripe subscription.deleted %s: no matching user', sub_id)
