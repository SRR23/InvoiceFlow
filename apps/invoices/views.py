"""
Views for Invoice management.
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from utils.permissions import IsBusinessUser
from .models import Invoice, InvoiceItem
from .serializers import (
    InvoiceSerializer,
    InvoiceCreateSerializer,
    InvoiceItemSerializer,
    PublicInvoiceSerializer,
)


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoices.
    Only business users can access their own invoices.
    """
    permission_classes = [IsAuthenticated, IsBusinessUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'client', 'currency']
    search_fields = ['invoice_number', 'client__name', 'client__email']
    ordering_fields = ['created_at', 'due_date', 'total_amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return only invoices belonging to the current user."""
        return Invoice.objects.filter(user=self.request.user).select_related('client')
    
    def get_serializer_class(self):
        """Use different serializers for create vs retrieve/update."""
        if self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer
    
    def perform_create(self, serializer):
        """Set the user when creating a new invoice."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """Send invoice via email (Celery task)."""
        invoice = self.get_object()
        # TODO: Trigger Celery task to send email
        return Response({'message': 'Invoice email will be sent shortly'})
    
    @action(detail=True, methods=['post'])
    def mark_sent(self, request, pk=None):
        """Mark invoice as sent."""
        invoice = self.get_object()
        invoice.status = 'SENT'
        invoice.save()
        return Response(InvoiceSerializer(invoice).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an invoice."""
        invoice = self.get_object()
        if invoice.status == 'PAID':
            return Response(
                {'error': 'Cannot cancel a paid invoice'},
                status=status.HTTP_400_BAD_REQUEST
            )
        invoice.status = 'CANCELLED'
        invoice.save()
        return Response(InvoiceSerializer(invoice).data)


class InvoiceItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing invoice items.
    """
    serializer_class = InvoiceItemSerializer
    permission_classes = [IsAuthenticated, IsBusinessUser]
    
    def get_queryset(self):
        """Return items for invoices belonging to the current user."""
        invoice_id = self.request.query_params.get('invoice_id')
        if invoice_id:
            return InvoiceItem.objects.filter(
                invoice_id=invoice_id,
                invoice__user=self.request.user
            )
        return InvoiceItem.objects.filter(invoice__user=self.request.user)
    
    def perform_create(self, serializer):
        """Validate that invoice belongs to user before creating item."""
        invoice_id = self.request.data.get('invoice')
        invoice = Invoice.objects.get(id=invoice_id, user=self.request.user)
        serializer.save(invoice=invoice)


class PublicInvoiceView(generics.RetrieveAPIView):
    """
    Public endpoint for viewing invoice by public_id.
    No authentication required.
    """
    queryset = Invoice.objects.all()
    serializer_class = PublicInvoiceSerializer
    permission_classes = [AllowAny]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
