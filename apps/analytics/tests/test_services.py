"""Unit tests for analytics calculations."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.analytics.services import AnalyticsService
from tests.factories import InvoiceFactory, PaymentFactory, UserFactory
from utils.constants import (
    INVOICE_STATUS_DRAFT,
    INVOICE_STATUS_PAID,
    INVOICE_STATUS_SENT,
    PAYMENT_STATUS_COMPLETED,
)


@pytest.mark.django_db
class TestAnalyticsService:
    def test_calculate_user_analytics(self):
        user = UserFactory()
        InvoiceFactory(user=user, status=INVOICE_STATUS_PAID, invoice_number="INV-000001")
        InvoiceFactory(user=user, status=INVOICE_STATUS_SENT, invoice_number="INV-000002")
        InvoiceFactory(user=user, status=INVOICE_STATUS_DRAFT, invoice_number="INV-000003")
        paid_invoice = InvoiceFactory(
            user=user, status=INVOICE_STATUS_PAID, invoice_number="INV-000004"
        )
        PaymentFactory(
            invoice=paid_invoice,
            amount=Decimal("150.00"),
            status=PAYMENT_STATUS_COMPLETED,
            paid_at=timezone.now(),
            transaction_id="txn_analytics_1",
        )

        analytics = AnalyticsService.calculate_user_analytics(user)
        assert analytics.total_invoices == 4
        assert analytics.paid_invoices == 2
        assert analytics.pending_invoices == 2
        assert analytics.total_revenue == Decimal("150.00")
