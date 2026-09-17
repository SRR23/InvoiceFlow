"""Unit tests for shared DRF permissions."""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from tests.factories import InvoiceFactory, UserFactory
from utils.constants import SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_NONE
from utils.permissions import IsBusinessUser, IsOwner


def _request(user):
    return SimpleNamespace(user=user)


@pytest.mark.django_db
class TestIsBusinessUser:
    def test_allows_business_user_on_trial(self):
        user = UserFactory()
        assert user.trial_ends_at is not None
        assert user.trial_ends_at > timezone.now()
        assert IsBusinessUser().has_permission(_request(user), None) is True

    def test_rejects_non_business_user(self):
        user = UserFactory(is_business_user=False)
        assert IsBusinessUser().has_permission(_request(user), None) is False

    def test_rejects_expired_trial_without_subscription(self):
        user = UserFactory(
            trial_ends_at=timezone.now() - timedelta(days=1),
            subscription_status=SUBSCRIPTION_STATUS_NONE,
        )
        permission = IsBusinessUser()
        assert permission.has_permission(_request(user), None) is False
        assert "trial" in permission.message.lower() or "subscription" in permission.message.lower()

    def test_allows_active_subscription_after_trial(self):
        user = UserFactory(
            trial_ends_at=timezone.now() - timedelta(days=1),
            subscription_status=SUBSCRIPTION_STATUS_ACTIVE,
        )
        assert IsBusinessUser().has_permission(_request(user), None) is True

    def test_allows_staff_even_if_trial_expired(self):
        user = UserFactory(
            is_staff=True,
            trial_ends_at=timezone.now() - timedelta(days=1),
            subscription_status=SUBSCRIPTION_STATUS_NONE,
        )
        assert IsBusinessUser().has_permission(_request(user), None) is True


@pytest.mark.django_db
class TestIsOwner:
    def test_owner_of_invoice(self):
        invoice = InvoiceFactory()
        assert IsOwner().has_object_permission(_request(invoice.user), None, invoice) is True

    def test_non_owner_denied(self):
        invoice = InvoiceFactory()
        other = UserFactory()
        assert IsOwner().has_object_permission(_request(other), None, invoice) is False

    def test_owner_via_invoice_item(self):
        from tests.factories import InvoiceItemFactory

        item = InvoiceItemFactory()
        assert IsOwner().has_object_permission(_request(item.invoice.user), None, item) is True
