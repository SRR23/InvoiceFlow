"""Unit tests for payment-link policy helpers."""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.payments.payment_link_policy import (
    assert_may_create_payment_link,
    is_invoice_past_due,
    stripe_checkout_expires_at_unix,
)


def _invoice(*, status="SENT", due_offset_days=7):
    return SimpleNamespace(
        status=status,
        due_date=(timezone.now() + timedelta(days=due_offset_days)).date(),
    )


@pytest.mark.django_db
class TestPaymentLinkPolicy:
    def test_past_due_detection(self):
        invoice = _invoice(due_offset_days=-1)
        assert is_invoice_past_due(invoice) is True

    def test_blocks_paid_invoice(self):
        with pytest.raises(ValueError, match="already paid"):
            assert_may_create_payment_link(_invoice(status="PAID"))

    def test_blocks_past_due_invoice(self):
        with pytest.raises(ValueError, match="past its due date"):
            assert_may_create_payment_link(_invoice(due_offset_days=-2))

    def test_stripe_expires_at_within_24h_window(self):
        invoice = _invoice(due_offset_days=10)
        expires = stripe_checkout_expires_at_unix(invoice)
        now_ts = int(timezone.now().timestamp())
        assert now_ts + 30 * 60 <= expires <= now_ts + 24 * 60 * 60 + 5
