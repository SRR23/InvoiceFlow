"""
URL configuration for InvoiceFlow project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/clients/', include('apps.clients.urls')),
    path('api/invoices/', include('apps.invoices.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/public/', include('apps.invoices.public_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
