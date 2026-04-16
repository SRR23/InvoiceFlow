"""
Development settings for InvoiceFlow project.
"""
import os

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Development-specific CORS settings
CORS_ALLOW_ALL_ORIGINS = True

# Default: console (no real send). If RESEND_API_KEY is set in the environment (e.g. .env), use Resend
# so local dev matches production without setting EMAIL_BACKEND manually.
if os.environ.get('EMAIL_BACKEND') is None:
    if os.environ.get('RESEND_API_KEY', '').strip():
        EMAIL_BACKEND = 'utils.email_backends.resend_backend.ResendEmailBackend'
    else:
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development-specific logging
LOGGING['loggers']['apps']['level'] = 'DEBUG'

# Disable SSL verification for development (if needed)
SSLCOMMERZ_IS_LIVE = False
