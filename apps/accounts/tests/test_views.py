"""API tests for auth endpoints."""
from __future__ import annotations

import pytest
from django.urls import reverse

from tests.factories import UserFactory


@pytest.mark.django_db
class TestRegisterLogin:
    def test_register_creates_business_user(self, api_client):
        url = reverse("accounts:register")
        payload = {
            "email": "newbiz@example.com",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
            "first_name": "New",
            "last_name": "Biz",
            "company_name": "New Biz LLC",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == 201
        assert response.data["user"]["email"] == "newbiz@example.com"
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]


    def test_register_rejects_mismatched_passwords(self, api_client):
        url = reverse("accounts:register")
        payload = {
            "email": "bad@example.com",
            "password": "StrongPass123!",
            "password2": "DifferentPass123!",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == 400

    def test_login_returns_tokens(self, api_client):
        UserFactory(email="login@example.com", password="StrongPass123!")
        url = reverse("accounts:login")
        response = api_client.post(
            url,
            {"email": "login@example.com", "password": "StrongPass123!"},
            format="json",
        )
        assert response.status_code == 200
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]


    def test_profile_requires_auth(self, api_client):
        url = reverse("accounts:profile")
        assert api_client.get(url).status_code == 401

    def test_profile_returns_current_user(self, auth_client, business_user):
        url = reverse("accounts:profile")
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.data["email"] == business_user.email
        assert response.data["is_business_user"] is True
