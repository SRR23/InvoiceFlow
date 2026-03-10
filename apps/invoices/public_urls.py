from django.urls import path
from .views import PublicInvoiceView

app_name = 'public'

urlpatterns = [
    path('invoice/<uuid:public_id>/', PublicInvoiceView.as_view(), name='public-invoice'),
]
