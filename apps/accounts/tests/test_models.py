"""Unit tests for User model behaviour."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.factories import UserFactory
from utils.constants import SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_NONE


@pytest.mark.django_db
class TestUserModel:
    def test_new_business_user_gets_trial_window(self):
        user = UserFactory()
        assert user.trial_ends_at is not None
        assert user.trial_ends_at > timezone.now()
        assert user.has_active_app_access() is True

    def test_email_is_username(self):
        user = UserFactory(email="owner@example.com")
        assert str(user) == "owner@example.com"
        assert user.get_username() == "owner@example.com"

    def test_has_active_app_access_with_paid_status(self):
        user = UserFactory(
            trial_ends_at=timezone.now() - timedelta(days=5),
            subscription_status=SUBSCRIPTION_STATUS_ACTIVE,
        )
        assert user.has_active_app_access() is True

    def test_has_active_app_access_false_when_trial_and_sub_inactive(self):
        user = UserFactory(
            trial_ends_at=timezone.now() - timedelta(days=5),
            subscription_status=SUBSCRIPTION_STATUS_NONE,
        )
        assert user.has_active_app_access() is False
