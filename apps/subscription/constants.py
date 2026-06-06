from django.db import models
from django.utils.translation import gettext_lazy as _


class SubscriptionStatus(models.TextChoices):
    TRIAL = "trial", _("Trial")
    ACTIVE = "active", _("Active")
    CANCELLED = "cancelled", _("Cancelled")
    EXPIRED = "expired", _("Expired")


class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ISSUED = "ISSUED", "Issued"
    PAID = "PAID", "Paid"
    VOID = "VOID", "Void"
    FAILED = "FAILED", "Failed"


