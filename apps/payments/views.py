"""
Views for Payment processing and webhooks.
"""
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, OpenApiResponse
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


@extend_schema(
    tags=['Payments'],
    summary='Create Stripe payment',
    description='Create a Stripe checkout session for an invoice.',
    request={
        'type': 'object',
        'properties': {
            'invoice_id': {'type': 'integer'},
        },
        'required': ['invoice_id']
    },
    responses={
        200: OpenApiResponse(
            description='Checkout session created',
            response={
                'type': 'object',
                'properties': {
                    'checkout_url': {'type': 'string', 'format': 'uri'},
                    'invoice_id': {'type': 'integer'},
                }
            }
        ),
        400: OpenApiResponse(description='Invalid request or invoice already paid'),
        404: OpenApiResponse(description='Invoice not found'),
    }
)
class CreateStripePaymentView(APIView):
    """Create a Stripe checkout session for an invoice."""
    permission_classes = [IsAuthenticated, IsBusinessUser]
    
    def post(self, request):
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


@extend_schema(
    tags=['Payments'],
    summary='Create SSLCommerz payment',
    description='Create an SSLCommerz payment session for an invoice.',
    request={
        'type': 'object',
        'properties': {
            'invoice_id': {'type': 'integer'},
        },
        'required': ['invoice_id']
    },
    responses={
        200: OpenApiResponse(
            description='Payment session created',
            response={
                'type': 'object',
                'properties': {
                    'redirect_url': {'type': 'string', 'format': 'uri'},
                    'payment_data': {'type': 'object'},
                }
            }
        ),
        400: OpenApiResponse(description='Invalid request or invoice already paid'),
        404: OpenApiResponse(description='Invoice not found'),
    }
)
class CreateSSLCommerzPaymentView(APIView):
    """Create an SSLCommerz payment session for an invoice."""
    permission_classes = [IsAuthenticated, IsBusinessUser]
    
    def post(self, request):
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


@extend_schema(
    tags=['Webhooks'],
    summary='Stripe webhook',
    description='Handle Stripe webhook events. This endpoint is called by Stripe.',
    request={
        'type': 'object',
        'description': 'Stripe webhook payload'
    },
    responses={
        200: OpenApiResponse(description='Webhook received and processed'),
    },
    exclude=True  # Hide from Swagger UI as it's for external services
)
@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
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


@extend_schema(
    tags=['Webhooks'],
    summary='SSLCommerz IPN',
    description='Handle SSLCommerz IPN (Instant Payment Notification). This endpoint is called by SSLCommerz.',
    request={
        'type': 'object',
        'description': 'SSLCommerz IPN payload'
    },
    responses={
        200: OpenApiResponse(description='IPN received and processed'),
    },
    exclude=True  # Hide from Swagger UI as it's for external services
)
@method_decorator(csrf_exempt, name='dispatch')
class SSLCommerzWebhookView(APIView):
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
