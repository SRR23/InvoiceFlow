from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from utils.constants import SUBSCRIPTION_STATUS_NONE


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_business_user', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model that uses email instead of username.
    Supports Google OAuth login via google_id field.
    """
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    # Google OAuth
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # Business user flag - only business users can access business APIs
    is_business_user = models.BooleanField(default=True)
    
    # Django default fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    # Optional business fields
    company_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    currency = models.CharField(max_length=3, default='USD', help_text='ISO 4217 currency code')

    # Next sequence for server-assigned invoice numbers (INV-000001 style), incremented under row lock.
    invoice_number_next = models.PositiveIntegerField(
        default=1,
        help_text='Next numeric suffix for auto-generated invoice numbers for this account',
    )

    # SaaS subscription (platform Stripe). Trial is set on first save for new business users.
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Business features allowed before this instant without a paid Stripe subscription.',
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, default='')
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default='')
    subscription_status = models.CharField(
        max_length=32,
        default=SUBSCRIPTION_STATUS_NONE,
        db_index=True,
        help_text='Stripe subscription.status (e.g. active, canceled) or none for the monthly SaaS plan.',
    )

    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['google_id']),
        ]
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the full name of the user."""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email

    def save(self, *args, **kwargs):
        """Start a trial window for new business accounts (not staff/superuser)."""
        if (
            self._state.adding
            and self.trial_ends_at is None
            and self.is_business_user
            and not (self.is_staff or self.is_superuser)
        ):
            days = int(getattr(settings, 'DEFAULT_TRIAL_DAYS', 30))
            self.trial_ends_at = timezone.now() + timedelta(days=days)
        super().save(*args, **kwargs)

    def has_active_app_access(self) -> bool:
        """
        Business APIs require trial OR an active-enough Stripe subscription.
        Staff/superuser always allowed; non-business users are not gated here.
        """
        from utils.constants import (
            SUBSCRIPTION_STATUS_ACTIVE,
            SUBSCRIPTION_STATUS_TRIALING,
        )

        if not self.is_business_user:
            return True
        if self.is_staff or self.is_superuser:
            return True
        now = timezone.now()
        if self.trial_ends_at and now < self.trial_ends_at:
            return True
        return self.subscription_status in (SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_TRIALING)


class PasswordResetOTP(models.Model):
    """
    Short-lived hashed OTP for forgot-password flow (one active row per user).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_reset_otps",
    )
    otp_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_reset_otps"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"PasswordResetOTP(user_id={self.user_id})"
