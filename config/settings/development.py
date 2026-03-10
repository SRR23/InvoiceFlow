"""
Development settings for InvoiceFlow project.
"""
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Development-specific CORS settings
CORS_ALLOW_ALL_ORIGINS = True

# Development email backend (console for testing)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development-specific logging
LOGGING['loggers']['apps']['level'] = 'DEBUG'

# Disable SSL verification for development (if needed)
SSLCOMMERZ_IS_LIVE = False
