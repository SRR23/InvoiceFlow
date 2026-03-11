from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PaymentViewSet,
    CreateStripePaymentView,
    CreateSSLCommerzPaymentView,
    StripeWebhookView,
    SSLCommerzWebhookView,
)

app_name = 'payments'

router = DefaultRouter()
router.register(r'', PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
    path('stripe/create/', CreateStripePaymentView.as_view(), name='stripe-create'),
    path('sslcommerz/create/', CreateSSLCommerzPaymentView.as_view(), name='sslcommerz-create'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('webhooks/sslcommerz/', SSLCommerzWebhookView.as_view(), name='sslcommerz-webhook'),
]
