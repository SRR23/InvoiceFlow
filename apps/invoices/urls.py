from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, InvoiceItemViewSet

app_name = 'invoices'

router = DefaultRouter()
router.register(r'', InvoiceViewSet, basename='invoice')
router.register(r'items', InvoiceItemViewSet, basename='invoice-item')

urlpatterns = [
    path('', include(router.urls)),
]
