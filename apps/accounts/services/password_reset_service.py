"""
Forgot-password flow: request OTP by email, verify OTP, confirm new password.

Security notes:
  - OTP is hashed at rest (HMAC-SHA256 with SECRET_KEY).
  - Request endpoint always returns the same message (no email enumeration).
  - After OTP verification, a short-lived signed token is returned for the final step.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from ..models import PasswordResetOTP, User

logger = logging.getLogger(__name__)

TOKEN_SALT = "invoiceflow.password-reset-confirm"
OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = 15
CONFIRM_TOKEN_MAX_AGE_SECONDS = 15 * 60
OTP_MAX_ATTEMPTS = 5

# Rate limits (per normalized email address)
REQUEST_COOLDOWN_SECONDS = 60
REQUEST_HOURLY_MAX = 5
VERIFY_LOCKOUT_SECONDS = 15 * 60
VERIFY_ATTEMPTS_MAX = 10  # per email, across requests (cache)


def normalize_otp_input(raw: str) -> str:
    """Extract exactly 6 digits from user input (allows spaces or dashes)."""
    if not raw:
        return ""
    digits = "".join(c for c in str(raw) if c.isdigit())
    return digits


def _otp_hmac(otp_plain: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        otp_plain.encode(),
        hashlib.sha256,
    ).hexdigest()


def _cache_key_cooldown(email_key: str) -> str:
    return f"pwreset:cool:{email_key}"


def _cache_key_hourly(email_key: str) -> str:
    return f"pwreset:hr:{email_key}"


def _cache_key_verify_fails(email_key: str) -> str:
    return f"pwreset:vfails:{email_key}"


def _email_key(email: str) -> str:
    return User.objects.normalize_email(email).lower()


def check_request_rate_limit(email: str) -> None:
    """
    Raises ValueError with a safe user message if rate limited.
    """
    key = _email_key(email)
    if cache.get(_cache_key_cooldown(key)):
        raise ValueError(
            "Please wait a minute before requesting another code."
        )
    hourly = cache.get(_cache_key_hourly(key), 0)
    if hourly >= REQUEST_HOURLY_MAX:
        raise ValueError(
            "Too many reset requests for this email. Try again in an hour."
        )


def register_request_attempt(email: str) -> None:
    key = _email_key(email)
    cache.set(_cache_key_cooldown(key), 1, REQUEST_COOLDOWN_SECONDS)
    hourly_key = _cache_key_hourly(key)
    try:
        cache.incr(hourly_key)
    except ValueError:
        cache.set(hourly_key, 1, 3600)


def create_and_send_otp(user: User) -> None:
    """Replace any pending OTP for this user and email a new code."""
    otp_plain = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"
    otp_hash = _otp_hmac(otp_plain)
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRE_MINUTES)

    with transaction.atomic():
        PasswordResetOTP.objects.filter(user=user).delete()
        PasswordResetOTP.objects.create(
            user=user,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0,
        )

    subject = "Your password reset code"
    body = (
        f"Hello,\n\n"
        f"Your password reset verification code is: {otp_plain}\n\n"
        f"This code expires in {OTP_EXPIRE_MINUTES} minutes.\n"
        f"If you did not request this, you can ignore this email.\n"
    )
    from_email = getattr(
        settings,
        "DEFAULT_FROM_EMAIL",
        "noreply@localhost",
    )
    try:
        send_mail(
            subject,
            body,
            from_email,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        PasswordResetOTP.objects.filter(user=user).delete()
        raise


def request_password_reset_otp(email: str) -> None:
    """
    Public entry: apply rate limits, create OTP for user if they exist and are active.
    Does not raise if user missing (caller returns generic message).
    """
    check_request_rate_limit(email)
    # Consume cooldown + hourly counter before emailing so failed sends cannot bypass limits.
    register_request_attempt(email)

    user = User.objects.filter(email__iexact=_email_key(email)).first()
    if not user or not user.is_active:
        return

    try:
        create_and_send_otp(user)
    except Exception:
        logger.exception("Password reset email failed for user id=%s", user.pk)
        raise


def _verify_otp_record(user: User, otp_plain: str) -> bool:
    row = PasswordResetOTP.objects.filter(user=user).first()
    if not row:
        return False
    if row.expires_at < timezone.now():
        row.delete()
        return False
    if row.attempts >= OTP_MAX_ATTEMPTS:
        row.delete()
        return False
    ok = hmac.compare_digest(row.otp_hash, _otp_hmac(otp_plain))
    if not ok:
        PasswordResetOTP.objects.filter(pk=row.pk).update(
            attempts=row.attempts + 1
        )
        return False
    row.delete()
    return True


def verify_otp_and_issue_token(email: str, otp: str) -> str:
    """
    Validate OTP for email; return signed password_reset_token.
    Raises ValueError with generic message on any failure.
    """
    digits = normalize_otp_input(otp)
    if len(digits) != OTP_LENGTH:
        raise ValueError(
            "Invalid or expired verification code."
        )

    email_key = _email_key(email)
    fail_key = _cache_key_verify_fails(email_key)
    failures = cache.get(fail_key, 0)
    if failures >= VERIFY_ATTEMPTS_MAX:
        raise ValueError(
            "Too many incorrect attempts. Request a new code."
        )

    user = User.objects.filter(email__iexact=email_key).first()
    if not user or not user.is_active:
        cache.set(fail_key, failures + 1, VERIFY_LOCKOUT_SECONDS)
        raise ValueError(
            "Invalid or expired verification code."
        )

    if not _verify_otp_record(user, digits):
        cache.set(fail_key, failures + 1, VERIFY_LOCKOUT_SECONDS)
        raise ValueError(
            "Invalid or expired verification code."
        )

    cache.delete(fail_key)
    return signing.dumps(
        {"uid": user.pk},
        salt=TOKEN_SALT,
    )


def reset_password_with_token(token: str, new_password: str) -> User:
    """
    Validate signed token and set the user's password.
    Raises ValueError for bad/expired token; ValidationError for password policy.
    """
    try:
        data = signing.loads(
            token,
            salt=TOKEN_SALT,
            max_age=CONFIRM_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired:
        raise ValueError(
            "This reset link has expired. Start again from the beginning."
        ) from None
    except signing.BadSignature:
        raise ValueError(
            "Invalid reset token. Start again from the beginning."
        ) from None

    uid = int(data["uid"])
    user = User.objects.filter(pk=uid, is_active=True).first()
    if not user:
        raise ValueError(
            "Invalid reset token. Start again from the beginning."
        )

    validate_password(new_password, user=user)

    user.set_password(new_password)
    user.save(update_fields=["password"])
    PasswordResetOTP.objects.filter(user=user).delete()
    return user
