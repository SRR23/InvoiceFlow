"""
Server-side invoice number allocation (per-user, concurrency-safe).
"""
from django.contrib.auth import get_user_model


def allocate_next_invoice_number(user):
    """
    Return the next INV-NNNNNN string for this user and advance the counter.

    Must be called inside transaction.atomic() so the user row lock and invoice
    creation are one atomic unit (no duplicate numbers under concurrency).
    """
    User = get_user_model()
    locked = User.objects.select_for_update().get(pk=user.pk)
    seq = locked.invoice_number_next
    locked.invoice_number_next = seq + 1
    locked.save(update_fields=['invoice_number_next'])
    return f'INV-{seq:06d}'
