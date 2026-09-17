"""Unit tests for SaaS subscription helpers (no live Stripe calls)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.subscription.services import (
    _billing_cycle_to_stripe_interval,
    _load_subscription_package,
    _subscription_line_item_from_package,
    apply_subscription_checkout_completed,
    mark_subscription_deleted,
    sync_subscription_from_stripe_payload,
)
from tests.factories import SubscriptionPackageFactory, UserFactory
from utils.constants import (
    SAAS_SUBSCRIPTION_CHECKOUT_PURPOSE,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_CANCELED,
    SUBSCRIPTION_STATUS_NONE,
)


class TestBillingCycleMapping:
    def test_known_cycles(self):
        assert _billing_cycle_to_stripe_interval("monthly") == "month"
        assert _billing_cycle_to_stripe_interval("yearly") == "year"
        assert _billing_cycle_to_stripe_interval("weekly") == "week"
        assert _billing_cycle_to_stripe_interval("daily") == "day"

    def test_unknown_defaults_to_month(self):
        assert _billing_cycle_to_stripe_interval("fortnightly") == "month"


@pytest.mark.django_db
class TestPackageHelpers:
    def test_load_package_by_code(self):
        pkg = SubscriptionPackageFactory(code="pro", price=Decimal("49.00"))
        loaded = _load_subscription_package("pro")
        assert loaded.id == pkg.id

    def test_load_unknown_package_raises(self):
        SubscriptionPackageFactory(code="starter")
        with pytest.raises(ValueError, match="Unknown or inactive"):
            _load_subscription_package("missing")

    def test_line_item_from_package(self):
        pkg = SubscriptionPackageFactory(
            code="pro",
            name="Pro Plan",
            price=Decimal("29.50"),
            currency="USD",
            billing_cycle="monthly",
        )
        line = _subscription_line_item_from_package(pkg)
        assert line["price_data"]["unit_amount"] == 2950
        assert line["price_data"]["currency"] == "usd"
        assert line["price_data"]["recurring"]["interval"] == "month"


@pytest.mark.django_db
class TestSubscriptionWebhookSync:
    @patch("apps.subscription.services.stripe.Subscription.retrieve")
    @patch("apps.subscription.services._set_stripe_platform_key")
    def test_apply_checkout_completed_updates_user(self, _set_key, retrieve):
        user = UserFactory()
        retrieve.return_value = {"status": "active"}
        session = {
            "mode": "subscription",
            "payment_status": "paid",
            "customer": "cus_test",
            "subscription": "sub_test",
            "metadata": {
                "user_id": str(user.id),
                "checkout_purpose": SAAS_SUBSCRIPTION_CHECKOUT_PURPOSE,
            },
        }
        apply_subscription_checkout_completed(session)
        user.refresh_from_db()
        assert user.stripe_customer_id == "cus_test"
        assert user.stripe_subscription_id == "sub_test"
        assert user.subscription_status == SUBSCRIPTION_STATUS_ACTIVE

    def test_sync_subscription_status(self):
        user = UserFactory(
            stripe_subscription_id="sub_abc",
            subscription_status=SUBSCRIPTION_STATUS_NONE,
        )
        sync_subscription_from_stripe_payload({"id": "sub_abc", "status": "active"})
        user.refresh_from_db()
        assert user.subscription_status == SUBSCRIPTION_STATUS_ACTIVE

    def test_mark_subscription_deleted(self):
        user = UserFactory(
            stripe_subscription_id="sub_del",
            subscription_status=SUBSCRIPTION_STATUS_ACTIVE,
        )
        mark_subscription_deleted({"id": "sub_del"})
        user.refresh_from_db()
        assert user.subscription_status == SUBSCRIPTION_STATUS_CANCELED
