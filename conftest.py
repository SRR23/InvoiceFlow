"""
Project-wide pytest setup for InvoiceFlow.

Uses ``config.settings.development`` and local Postgres via ``DB_*`` env vars.

Safety: ``DATABASE_URL`` is cleared before Django loads so pytest never creates a
``test_*`` database on a remote/SSL host (e.g. Render) that may be in ``.env``.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")

# Prefer explicit local credentials. Remote DATABASE_URL must not be used for tests.
os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

_db_host = (os.environ.get("DB_HOST") or "localhost").strip().lower()
if _db_host not in {"localhost", "127.0.0.1"}:
    raise RuntimeError(
        f"Refusing to run tests against remote DB_HOST={_db_host!r}. "
        "Set DB_HOST=localhost (or 127.0.0.1) for pytest."
    )


def pytest_load_initial_conftests(early_config, parser, args):
    """Runs before Django setup — keep DATABASE_URL cleared."""
    os.environ.pop("DATABASE_URL", None)


import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import ClientFactory, InvoiceFactory, UserFactory


@pytest.fixture(autouse=True)
def _test_runtime_settings(settings):
    """Keep tests offline-friendly without changing development.py."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "invoiceflow-tests",
        }
    }
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def business_user(db):
    """Business user still inside the trial window (default User.save trial)."""
    return UserFactory()


@pytest.fixture
def expired_trial_user(db):
    """Business user with expired trial and no paid subscription."""
    from datetime import timedelta

    from django.utils import timezone

    from utils.constants import SUBSCRIPTION_STATUS_NONE

    return UserFactory(
        trial_ends_at=timezone.now() - timedelta(days=1),
        subscription_status=SUBSCRIPTION_STATUS_NONE,
    )


@pytest.fixture
def non_business_user(db):
    return UserFactory(is_business_user=False)


@pytest.fixture
def auth_client(api_client, business_user):
    """APIClient authenticated with a JWT for ``business_user``."""
    refresh = RefreshToken.for_user(business_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client.user = business_user
    return api_client


@pytest.fixture
def client_for_user(business_user):
    return ClientFactory(user=business_user)


@pytest.fixture
def invoice_for_user(business_user, client_for_user):
    return InvoiceFactory(user=business_user, client=client_for_user)
