"""API tests for client CRUD ownership."""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import ClientFactory, UserFactory


@pytest.mark.django_db
class TestClientAPI:
    def test_create_client(self, auth_client, business_user):
        url = reverse("clients:client-list")
        response = auth_client.post(
            url,
            {
                "name": "Acme Corp",
                "email": "billing@acme.test",
                "phone": "555-1000",
                "company": "Acme",
                "address": "1 Road",
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.data["name"] == "Acme Corp"
        assert business_user.clients.filter(name="Acme Corp").exists()

    def test_list_only_own_clients(self, auth_client, business_user):
        ClientFactory(user=business_user, name="Mine")
        other = UserFactory()
        ClientFactory(user=other, name="Theirs")

        response = auth_client.get(reverse("clients:client-list"))
        assert response.status_code == 200
        names = [row["name"] for row in response.data["results"]]
        assert "Mine" in names
        assert "Theirs" not in names

    def test_expired_trial_blocked(self, api_client, expired_trial_user):
        refresh = RefreshToken.for_user(expired_trial_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        response = api_client.get(reverse("clients:client-list"))
        assert response.status_code == 403
