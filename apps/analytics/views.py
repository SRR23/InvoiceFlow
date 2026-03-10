"""
Views for Analytics and Dashboard.
"""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from utils.permissions import IsBusinessUser
from .models import InvoiceAnalytics
from .serializers import InvoiceAnalyticsSerializer
from .services import AnalyticsService


class DashboardStatsView(generics.RetrieveAPIView):
    """
    Get dashboard statistics for the current user.
    Uses caching for performance.
    """
    permission_classes = [IsAuthenticated, IsBusinessUser]
    serializer_class = InvoiceAnalyticsSerializer
    
    def get_object(self):
        """Get or create analytics for the user, with caching."""
        cache_key = f"dashboard_stats_{self.request.user.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Get or create analytics
        analytics, created = InvoiceAnalytics.objects.get_or_create(user=self.request.user)
        
        # Recalculate if needed (older than 10 minutes)
        if not created and (timezone.now() - analytics.last_updated) > timedelta(minutes=10):
            AnalyticsService.calculate_user_analytics(self.request.user)
            analytics.refresh_from_db()
        
        # Cache for 10 minutes
        cache.set(cache_key, analytics, 600)
        
        return analytics


class RevenueReportView(generics.GenericAPIView):
    """
    Get revenue report with date range filtering.
    """
    permission_classes = [IsAuthenticated, IsBusinessUser]
    
    def get(self, request):
        """Get revenue report."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        report = AnalyticsService.get_revenue_report(
            user=request.user,
            start_date=start_date,
            end_date=end_date
        )
        
        return Response(report)
