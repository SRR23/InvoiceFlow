"""
Helper functions and utilities.
"""
import uuid
from datetime import datetime
from django.utils import timezone


def generate_invoice_number(user_id, prefix='INV'):
    """
    Generate a unique invoice number.
    Format: INV-{YYYYMMDD}-{USER_ID}-{RANDOM}
    """
    date_str = timezone.now().strftime('%Y%m%d')
    random_str = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{date_str}-{user_id}-{random_str}"


def format_currency(amount, currency='USD'):
    """
    Format currency amount for display.
    """
    currency_symbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'BDT': '৳',
    }
    
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"


def calculate_tax(amount, tax_rate):
    """
    Calculate tax amount from base amount and tax rate.
    """
    return (amount * tax_rate) / 100


def is_overdue(due_date):
    """
    Check if a due date has passed.
    """
    return due_date < timezone.now().date()


def get_invoice_public_url(public_id, base_url=None):
    """
    Generate public invoice URL.
    """
    from django.conf import settings
    base = base_url or settings.FRONTEND_URL
    return f"{base}/invoice/{public_id}"
