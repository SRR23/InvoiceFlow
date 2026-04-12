"""
Rules for when hosted payment links may be created and shown.

- **Due date:** Links are treated as valid only until the end of the invoice due date
  (23:59:59 in the default Django timezone). After that, we hide them and block new ones.

- **Paid:** Completed payments remove the link from the pending list (existing behavior).

- **Stripe:** Checkout Session ``expires_at`` must be between 30 minutes and 24 hours from
  creation (Stripe API). We set it to the earlier of: end of due date, or 24 hours from
  now. If the due date is more than 24 hours away, the Stripe URL still expires in 24 hours;
  the merchant can generate a new link before the due date.

- **SSLCommerz:** Hosted session lifetime is controlled by the gateway; we enforce due-date
  rules in our app (hide / block after due date).
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from django.utils import timezone


def end_of_invoice_due_date(invoice) -> datetime:
    """End of the invoice due calendar day in the active Django timezone."""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(
        datetime.combine(invoice.due_date, time(23, 59, 59)),
        tz,
    )


def is_invoice_past_due(invoice) -> bool:
    """True if today is after the invoice due date (calendar comparison)."""
    return timezone.now().date() > invoice.due_date


def assert_may_create_payment_link(invoice) -> None:
    """Raise ValueError if a new hosted payment session must not be created."""
    if invoice.status == "PAID":
        raise ValueError("Invoice is already paid.")
    if is_invoice_past_due(invoice):
        raise ValueError(
            "This invoice is past its due date; payment links can no longer be created."
        )


def stripe_checkout_expires_at_unix(invoice) -> int:
    """
    Unix timestamp for Stripe Checkout Session ``expires_at``.

    Stripe requires the session to expire between 30 minutes and 24 hours from creation.
    We pick the earlier of: end of due date, or 24 hours from now.

    Call :func:`assert_may_create_payment_link` before this.
    """
    now = timezone.now()
    due_end = end_of_invoice_due_date(invoice)

    stripe_min = now + timedelta(minutes=30)
    stripe_max = now + timedelta(hours=24)
    target = min(due_end, stripe_max)

    if target < stripe_min:
        raise ValueError(
            "Cannot create a Stripe session: the due time is within the next 30 minutes, "
            "which is below Stripe’s minimum checkout session length. Try again earlier."
        )

    return int(target.timestamp())
