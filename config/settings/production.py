"""
Production settings for InvoiceFlow project.
"""
from .base import *
import os
from urllib.parse import urlparse

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False


def _production_allowed_hosts():
    """
    Build ALLOWED_HOSTS from env, with Render-friendly fallbacks.

    Render sets ``RENDER_EXTERNAL_URL`` on web services. If ``ALLOWED_HOSTS`` is
    missing, not visible to the process, or has stray whitespace, the hostname
    from that URL still allows the service URL. Also honors ``RENDER_EXTERNAL_HOSTNAME``.
    """
    hosts = [
        h.strip()
        for h in os.environ.get('ALLOWED_HOSTS', '').split(',')
        if h.strip()
    ]
    render_url = os.environ.get('RENDER_EXTERNAL_URL', '').strip()
    if render_url:
        try:
            hostname = urlparse(render_url).hostname
            if hostname and hostname not in hosts:
                hosts.append(hostname)
        except ValueError:
            pass
    render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
    if render_host and render_host not in hosts:
        hosts.append(render_host)
    return hosts


ALLOWED_HOSTS = _production_allowed_hosts()

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
