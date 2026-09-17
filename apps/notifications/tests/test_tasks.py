"""Smoke tests for notification helpers (no real email send)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core import mail

from apps.notifications.tasks import _merchant_name, _pending_payment_links_for_invoice
from tests.factories import InvoiceFactory, PaymentFactory, UserFactory
from utils.constants import PAYMENT_STATUS_PENDING


@pytest.mark.django_db
class TestNotificationHelpers:
    def test_merchant_name_prefers_company(self):
        user = UserFactory(company_name="Bright Studio", first_name="A", last_name="B")
        assert _merchant_name(user) == "Bright Studio"

    def test_pending_payment_links_for_invoice(self):
        invoice = InvoiceFactory()
        PaymentFactory(
            invoice=invoice,
            status=PAYMENT_STATUS_PENDING,
            payment_url="https://pay.example/checkout",
            transaction_id="txn_link_1",
        )
        PaymentFactory(
            invoice=invoice,
            status=PAYMENT_STATUS_PENDING,
            payment_url="",
            transaction_id="txn_link_2",
        )
        links = _pending_payment_links_for_invoice(invoice.id)
        assert len(links) == 1
        assert links[0]["url"] == "https://pay.example/checkout"


@pytest.mark.django_db
class TestSendInvoiceEmailTask:
    @patch("apps.notifications.tasks.build_invoice_pdf_bytes", return_value=b"%PDF-fake")
    def test_send_invoice_email_queues_message(self, _pdf):
        from apps.notifications.tasks import send_invoice_email

        invoice = InvoiceFactory()
        invoice.client.email = "payer@example.com"
        invoice.client.save(update_fields=["email"])

        send_invoice_email(invoice.id)

        assert len(mail.outbox) == 1
        assert "payer@example.com" in mail.outbox[0].to
