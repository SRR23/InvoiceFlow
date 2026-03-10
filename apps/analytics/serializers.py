"""
Serializers for Analytics.
"""
from rest_framework import serializers
from .models import InvoiceAnalytics


class InvoiceAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for InvoiceAnalytics model."""
    
    class Meta:
        model = InvoiceAnalytics
        fields = (
            'total_invoices', 'total_revenue', 'paid_invoices',
            'pending_invoices', 'overdue_invoices', 'last_updated'
        )
