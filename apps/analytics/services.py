"""
Analytics service for calculating dashboard stats and reports.
"""
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from apps.invoices.models import Invoice
from apps.payments.models import Payment
from .models import InvoiceAnalytics


class AnalyticsService:
    """Service for calculating analytics and reports."""
    
    @staticmethod
    def calculate_user_analytics(user):
        """
        Calculate and update analytics for a user.
        """
        invoices = Invoice.objects.filter(user=user)
        
        total_invoices = invoices.count()
        paid_invoices = invoices.filter(status='PAID').count()
        pending_invoices = invoices.filter(status__in=['DRAFT', 'SENT']).count()
        overdue_invoices = invoices.filter(
            status__in=['SENT'],
            due_date__lt=timezone.now().date()
        ).count()
        
        # Calculate total revenue from paid invoices
        total_revenue = Payment.objects.filter(
            invoice__user=user,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Update or create analytics
        analytics, created = InvoiceAnalytics.objects.get_or_create(user=user)
        analytics.total_invoices = total_invoices
        analytics.paid_invoices = paid_invoices
        analytics.pending_invoices = pending_invoices
        analytics.overdue_invoices = overdue_invoices
        analytics.total_revenue = total_revenue
        analytics.save()
        
        return analytics
    
    @staticmethod
    def get_revenue_report(user, start_date=None, end_date=None):
        """
        Get revenue report for a user within a date range.
        """
        payments = Payment.objects.filter(
            invoice__user=user,
            status='completed'
        )
        
        if start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                payments = payments.filter(paid_at__date__gte=start)
            except ValueError:
                pass
        
        if end_date:
            try:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                payments = payments.filter(paid_at__date__lte=end)
            except ValueError:
                pass
        
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        payment_count = payments.count()
        
        # Group by date
        daily_revenue = payments.values('paid_at__date').annotate(
            daily_total=Sum('amount'),
            count=Count('id')
        ).order_by('paid_at__date')
        
        return {
            'total_revenue': float(total_revenue),
            'payment_count': payment_count,
            'start_date': start_date,
            'end_date': end_date,
            'daily_revenue': list(daily_revenue)
        }
