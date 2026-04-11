"""
Fernet-based encryption for per-tenant gateway secrets at rest.

Set PAYMENT_GATEWAY_FERNET_KEY to a Fernet key from ``Fernet.generate_key().decode()``
for production; if unset, a deterministic key is derived from Django SECRET_KEY
(so rotating SECRET_KEY will invalidate stored secrets).
"""
import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    explicit = getattr(settings, "PAYMENT_GATEWAY_FERNET_KEY", "") or ""
    if explicit.strip():
        key = explicit.strip().encode()
    else:
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    if plain is None or plain == "":
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    if token is None or token == "":
        return ""
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
