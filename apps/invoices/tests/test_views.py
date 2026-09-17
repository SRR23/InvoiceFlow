"""API tests for invoices and public links."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.factories import InvoiceFactory


@pytest.mark.django_db
class TestInvoiceAPI:
    def test_create_invoice_assigns_number(self, auth_client, business_user, client_for_user):
        url = reverse("invoices:invoice-list")
        payload = {
            "client": client_for_user.id,
            "issue_date": timezone.now().date().isoformat(),
            "due_date": (timezone.now() + timedelta(days=7)).date().isoformat(),
            "status": "DRAFT",
            "discount": "0.00",
            "currency": "USD",
            "notes": "",
            "items": [
                {
                    "title": "Design",
                    "description": "Logo",
                    "quantity": "1.00",
                    "unit_price": "250.00",
                    "tax_rate": "0.00",
                }
            ],
        }
        response = auth_client.post(url, payload, format="json")
        assert response.status_code == 201
        assert response.data["invoice_number"] == "INV-000001"
        business_user.refresh_from_db()
        assert business_user.invoice_number_next == 2

    def test_mark_sent(self, auth_client, invoice_for_user):
        url = reverse("invoices:invoice-mark-sent", kwargs={"pk": invoice_for_user.pk})
        response = auth_client.post(url)
        assert response.status_code == 200
        assert response.data["status"] == "SENT"

    def test_cannot_cancel_paid_invoice(self, auth_client, invoice_for_user):
        invoice_for_user.status = "PAID"
        invoice_for_user.save(update_fields=["status"])
        url = reverse("invoices:invoice-cancel", kwargs={"pk": invoice_for_user.pk})
        response = auth_client.post(url)
        assert response.status_code == 400

    def test_public_invoice_accessible_without_auth(self, api_client, invoice_for_user):
        url = reverse(
            "public:public-invoice",
            kwargs={"public_id": invoice_for_user.public_id},
        )
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["invoice_number"] == invoice_for_user.invoice_number
        assert "public_id" not in response.data
