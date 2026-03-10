from django.urls import path
from .views import DashboardStatsView, RevenueReportView

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='dashboard'),
    path('revenue/', RevenueReportView.as_view(), name='revenue'),
]
