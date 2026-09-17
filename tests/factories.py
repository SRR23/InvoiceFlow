"""
Shared factory-boy factories for InvoiceFlow tests.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.clients.models import Client
from apps.invoices.models import Invoice, InvoiceItem
from apps.payments.models import Payment
from apps.subscription.models import SubscriptionPackage
from utils.constants import (
    INVOICE_STATUS_DRAFT,
    PAYMENT_GATEWAY_STRIPE,
    PAYMENT_STATUS_PENDING,
    SUBSCRIPTION_STATUS_NONE,
)

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = "Test"
    last_name = "User"
    company_name = "Test Co"
    is_business_user = True
    is_active = True
    currency = "USD"
    subscription_status = SUBSCRIPTION_STATUS_NONE

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "TestPass123!")
        # Allow tests to set trial_ends_at explicitly (including expired).
        trial_ends_at = kwargs.pop("trial_ends_at", None)
        user = model_class.objects.create_user(password=password, **kwargs)
        if trial_ends_at is not None:
            user.trial_ends_at = trial_ends_at
            user.save(update_fields=["trial_ends_at"])
        return user


class ClientFactory(DjangoModelFactory):
    class Meta:
        model = Client

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Client {n}")
    email = factory.Sequence(lambda n: f"client{n}@example.com")
    phone = "555-0100"
    company = "Client Corp"
    address = "123 Test Street"


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = Invoice

    user = factory.SubFactory(UserFactory)
    client = factory.LazyAttribute(lambda o: ClientFactory(user=o.user))
    invoice_number = factory.Sequence(lambda n: f"INV-{n:06d}")
    issue_date = factory.LazyFunction(lambda: timezone.now().date())
    due_date = factory.LazyFunction(lambda: (timezone.now() + timedelta(days=14)).date())
    status = INVOICE_STATUS_DRAFT
    discount = Decimal("0.00")
    currency = "USD"
    notes = ""


class InvoiceItemFactory(DjangoModelFactory):
    class Meta:
        model = InvoiceItem

    invoice = factory.SubFactory(InvoiceFactory)
    title = "Consulting"
    description = "Hourly work"
    quantity = Decimal("2.00")
    unit_price = Decimal("100.00")
    tax_rate = Decimal("10.00")


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = Payment

    invoice = factory.SubFactory(InvoiceFactory)
    gateway = PAYMENT_GATEWAY_STRIPE
    transaction_id = factory.Sequence(lambda n: f"txn_test_{n}")
    amount = Decimal("100.00")
    currency = "USD"
    status = PAYMENT_STATUS_PENDING
    payment_url = ""


class SubscriptionPackageFactory(DjangoModelFactory):
    class Meta:
        model = SubscriptionPackage

    code = factory.Sequence(lambda n: f"pkg_{n}")
    name = factory.Sequence(lambda n: f"Package {n}")
    description = "Test package"
    price = Decimal("29.00")
    currency = "USD"
    billing_cycle = "monthly"
    is_active = True
