from django.urls import path

from .views import SubscriptionCheckoutView, SubscriptionStatusView

app_name = 'subscription'

urlpatterns = [
    path('subscription/status/', SubscriptionStatusView.as_view(), name='subscription_status'),
    path('subscription/checkout/', SubscriptionCheckoutView.as_view(), name='subscription_checkout'),
]
