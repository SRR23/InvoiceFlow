"""
Views for Payment processing and webhooks.
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from utils.permissions import IsBusinessUser
from .models import Payment, WebhookEvent
from .serializers import PaymentSerializer, WebhookEventSerializer
from .services import StripeService, SSLCommerzService


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing payment history.
    Only business users can view their own payments.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsBusinessUser]
    
    def get_queryset(self):
        """Return only payments for invoices belonging to the current user."""
        return Payment.objects.filter(invoice__user=self.request.user).select_related('invoice')


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsBusinessUser])
def create_stripe_payment(request):
    """Create a Stripe checkout session for an invoice."""
    invoice_id = request.data.get('invoice_id')
    
    if not invoice_id:
        return Response(
            {'error': 'invoice_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from apps.invoices.models import Invoice
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
        
        if invoice.status == 'PAID':
            return Response(
                {'error': 'Invoice is already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create Stripe checkout session
        checkout_url = StripeService.create_checkout_session(invoice)
        
        return Response({
            'checkout_url': checkout_url,
            'invoice_id': invoice.id
        })
    except Invoice.DoesNotExist:
        return Response(
            {'error': 'Invoice not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsBusinessUser])
def create_sslcommerz_payment(request):
    """Create an SSLCommerz payment session for an invoice."""
    invoice_id = request.data.get('invoice_id')
    
    if not invoice_id:
        return Response(
            {'error': 'invoice_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from apps.invoices.models import Invoice
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
        
        if invoice.status == 'PAID':
            return Response(
                {'error': 'Invoice is already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create SSLCommerz payment session
        payment_data = SSLCommerzService.create_payment_session(invoice)
        
        return Response(payment_data)
    except Invoice.DoesNotExist:
        return Response(
            {'error': 'Invoice not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(generics.GenericAPIView):
    """Handle Stripe webhook events."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Process Stripe webhook."""
        # TODO: Implement Stripe webhook verification and processing
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        # Log webhook event
        event = WebhookEvent.objects.create(
            gateway='stripe',
            event_type=request.data.get('type', 'unknown'),
            payload=request.data
        )
        
        # TODO: Process webhook event
        # StripeService.process_webhook(event)
        
        return Response({'received': True})


@method_decorator(csrf_exempt, name='dispatch')
class SSLCommerzWebhookView(generics.GenericAPIView):
    """Handle SSLCommerz IPN (Instant Payment Notification)."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Process SSLCommerz IPN."""
        # TODO: Implement SSLCommerz IPN verification and processing
        event = WebhookEvent.objects.create(
            gateway='sslcommerz',
            event_type='payment_notification',
            payload=request.data
        )
        
        # TODO: Process webhook event
        # SSLCommerzService.process_ipn(event)
        
        return Response({'status': 'success'})
