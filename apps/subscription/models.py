from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import InvoiceStatus, SubscriptionStatus
from .utils import slug_utils


class TimeStampedModel(models.Model):
    """Replaces external ``BaseModel`` — timestamps only."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SubscriptionFeature(TimeStampedModel):
    """Feature flags / bullets attachable to packages (optional)."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'subscription_features'
        ordering = ['code']

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'


class SubscriptionPackage(TimeStampedModel):
    """
    Sellable plan row —     ``price`` / ``currency`` / ``billing_cycle`` feed Stripe Checkout
    ``price_data`` (see ``apps.subscription.services``).
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text='Stable id sent as ``package_code`` from the client (e.g. starter, pro).',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    billing_cycle = models.CharField(
        max_length=20,
        default='monthly',
        db_index=True,
        help_text='monthly, yearly, etc. — mapped to Stripe recurring.interval.',
    )
    features = models.ManyToManyField(SubscriptionFeature, related_name='packages', blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'subscription_packages'
        ordering = ['id']

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'


class Subscription(TimeStampedModel):
    """Per-user subscription instance (trial/active/etc.)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    package = models.ForeignKey(
        SubscriptionPackage,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
    )
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True, db_index=True)
    purchased_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions_purchased',
    )
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'subscriptions'
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(
                    status__in=[
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIAL,
                    ]
                ),
                name='uniq_active_or_trial_sub_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'current_period_end'], name='sub_status_periodend_idx'),
            models.Index(fields=['user', 'status', 'current_period_end'], name='sub_user_status_periodend_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.user_id} -> {self.package.name} ({self.status})'

    @property
    def is_current(self) -> bool:
        now = timezone.now()
        if self.current_period_end is None:
            return False
        return (
            self.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}
            and self.current_period_end >= now
        )


class SubscriptionInvoice(TimeStampedModel):
    """Internal billing document for a subscription period."""

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='invoices',
    )
    invoice_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.ISSUED,
        db_index=True,
    )
    issued_at = models.DateTimeField(default=timezone.now, db_index=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    payment_reference = models.CharField(max_length=255, blank=True, default='')
    package_code = models.CharField(max_length=50)
    package_name = models.CharField(max_length=100)
    package_price = models.DecimalField(max_digits=10, decimal_places=2)
    package_billing_cycle = models.CharField(max_length=20)
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'subscription_invoices'
        indexes = [
            models.Index(fields=['subscription', 'issued_at'], name='subinv_sub_issued_idx'),
            models.Index(fields=['status', 'issued_at'], name='subinv_status_issued_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.invoice_number} ({self.status})'

    def snapshot_from_package(self) -> None:
        pkg = self.subscription.package
        self.package_code = pkg.code
        self.package_name = pkg.name
        self.package_price = pkg.price
        self.package_billing_cycle = pkg.billing_cycle

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = slug_utils.generate_unique_invoice_code(
                SubscriptionInvoice, prefix='SUBINV'
            )
        if not self.package_code:
            self.snapshot_from_package()
        return super().save(*args, **kwargs)
