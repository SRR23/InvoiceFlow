from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreateSSLCommerzPaymentView,
    CreateStripePaymentView,
    MerchantGatewaySettingsView,
    PaymentViewSet,
    SSLCommerzMerchantWebhookView,
    SSLCommerzWebhookView,
    StripeMerchantWebhookView,
    StripeWebhookView,
)

app_name = 'payments'

router = DefaultRouter()
router.register(r'', PaymentViewSet, basename='payment')

# Specific paths must come before the router: otherwise ``gateway-settings`` is matched as
# PaymentViewSet detail PK and PATCH returns 405 (ReadOnlyModelViewSet).
urlpatterns = [
    path('gateway-settings/', MerchantGatewaySettingsView.as_view(), name='gateway-settings'),
    path('stripe/create/', CreateStripePaymentView.as_view(), name='stripe-create'),
    path('sslcommerz/create/', CreateSSLCommerzPaymentView.as_view(), name='sslcommerz-create'),
    path('webhooks/stripe/<uuid:webhook_key>/', StripeMerchantWebhookView.as_view(), name='stripe-webhook-merchant'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='stripe-webhook-legacy'),
    path(
        'webhooks/sslcommerz/<uuid:webhook_key>/',
        SSLCommerzMerchantWebhookView.as_view(),
        name='sslcommerz-webhook-merchant',
    ),
    path('webhooks/sslcommerz/', SSLCommerzWebhookView.as_view(), name='sslcommerz-webhook-legacy'),
    path('', include(router.urls)),
]
