
from django.db import models
from django.conf import settings


class Client(models.Model):
    """
    Client model representing a customer of a business user.
    Each business user can have multiple clients.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clients',
        help_text='The business user who owns this client'
    )
    name = models.CharField(max_length=255, help_text='Client full name')
    email = models.EmailField(blank=True, help_text='Client email address')
    phone = models.CharField(max_length=20, blank=True, help_text='Client phone number')
    company = models.CharField(max_length=255, blank=True, help_text='Client company name')
    address = models.TextField(blank=True, help_text='Client address')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.user.email})"
