"""
Views for Analytics and Dashboard.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from utils.permissions import IsBusinessUser
from .models import InvoiceAnalytics
from .serializers import InvoiceAnalyticsSerializer
from .services import AnalyticsService


@extend_schema(
    tags=['Analytics'],
    summary='Get dashboard statistics',
    description='Get dashboard statistics for the current user. Uses caching for performance.',
    responses={
        200: InvoiceAnalyticsSerializer,
    }
)
class DashboardStatsView(APIView):
    """
    Get dashboard statistics for the current user.
    Uses caching for performance.
    """
    permission_classes = [IsAuthenticated, IsBusinessUser]
    
    def get(self, request):
        """Get or create analytics for the user, with caching."""
        cache_key = f"dashboard_stats_{request.user.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            serializer = InvoiceAnalyticsSerializer(cached_data)
            return Response(serializer.data)
        
        # Get or create analytics
        analytics, created = InvoiceAnalytics.objects.get_or_create(user=request.user)
        
        # Recalculate if needed (older than 10 minutes)
        if not created and (timezone.now() - analytics.last_updated) > timedelta(minutes=10):
            AnalyticsService.calculate_user_analytics(request.user)
            analytics.refresh_from_db()
        
        # Cache for 10 minutes
        cache.set(cache_key, analytics, 600)
        
        serializer = InvoiceAnalyticsSerializer(analytics)
        return Response(serializer.data)


@extend_schema(
    tags=['Analytics'],
    summary='Get revenue report',
    description='Get revenue report with optional date range filtering.',
    parameters=[
        OpenApiParameter(
            name='start_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Start date (YYYY-MM-DD)',
            required=False,
        ),
        OpenApiParameter(
            name='end_date',
            type=str,
            location=OpenApiParameter.QUERY,
            description='End date (YYYY-MM-DD)',
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description='Revenue report',
            response={
                'type': 'object',
                'properties': {
                    'total_revenue': {'type': 'number'},
                    'payment_count': {'type': 'integer'},
                    'start_date': {'type': 'string', 'format': 'date'},
                    'end_date': {'type': 'string', 'format': 'date'},
                    'daily_revenue': {
                        'type': 'array',
                        'items': {'type': 'object'}
                    },
                }
            }
        ),
    }
)
class RevenueReportView(APIView):
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
