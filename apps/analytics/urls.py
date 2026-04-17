from django.urls import path
from .views import DashboardStatsView, RevenueReportView, health_check

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='dashboard'),
    path('revenue/', RevenueReportView.as_view(), name='revenue'),
    path('health/', health_check, name='health_check'),
]
