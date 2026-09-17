"""Unit tests for invoice number allocation and totals."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import transaction

from apps.invoices.invoice_numbers import allocate_next_invoice_number
from tests.factories import InvoiceFactory, InvoiceItemFactory, UserFactory


@pytest.mark.django_db
class TestInvoiceNumbers:
    def test_allocate_increments_per_user(self):
        user = UserFactory()
        assert user.invoice_number_next == 1
        with transaction.atomic():
            first = allocate_next_invoice_number(user)
            second = allocate_next_invoice_number(user)
        assert first == "INV-000001"
        assert second == "INV-000002"
        user.refresh_from_db()
        assert user.invoice_number_next == 3

    def test_counters_are_independent_per_user(self):
        user_a = UserFactory()
        user_b = UserFactory()
        with transaction.atomic():
            a_num = allocate_next_invoice_number(user_a)
            b_num = allocate_next_invoice_number(user_b)
        assert a_num == "INV-000001"
        assert b_num == "INV-000001"


@pytest.mark.django_db
class TestInvoiceTotals:
    def test_item_save_recalculates_invoice_totals(self):
        invoice = InvoiceFactory(discount=Decimal("10.00"))
        InvoiceItemFactory(
            invoice=invoice,
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
            tax_rate=Decimal("10.00"),
        )
        invoice.refresh_from_db()
        # subtotal = 100, tax = 10, discount = 10 => total 100
        assert invoice.subtotal == Decimal("100.00")
        assert invoice.tax == Decimal("10.00")
        assert invoice.total_amount == Decimal("100.00")
