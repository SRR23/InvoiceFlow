"""
Production settings for InvoiceFlow project.
"""
from .base import *
import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

print("DEBUG ALLOWED_HOSTS:", ALLOWED_HOSTS)

# Security settings for production
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Production CORS - must be explicit
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')

# Production logging
# LOGGING['handlers']['file']['filename'] = '/var/log/invoiceflow/django.log'
# LOGGING['loggers']['apps']['level'] = 'INFO'

# Enable SSLCommerz live mode in production
SSLCOMMERZ_IS_LIVE = True

# Static files served by web server in production
STATIC_ROOT = '/var/www/invoiceflow/staticfiles'
MEDIA_ROOT = '/var/www/invoiceflow/media'
