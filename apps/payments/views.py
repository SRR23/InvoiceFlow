import logging

import stripe
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from utils.permissions import IsBusinessUser
from .models import Payment, WebhookEvent
from .serializers import PaymentSerializer, WebhookEventSerializer
from .services import (
    PaymentGatewayMixin,
    SSLCommerzService,
    StripeService,
    stripe_event_to_dict,
)

logger = logging.getLogger(__name__)


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


def _flatten_drf_request_data(request):
    """Normalize DRF parsed body to a plain dict for JSONField storage."""
    data = request.data
    if hasattr(data, 'dict'):
        return data.dict()
    if isinstance(data, dict):
        return dict(data)
    return {}


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
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """Verify signature, persist event, update invoice/payment state."""
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.error('STRIPE_WEBHOOK_SECRET is not configured')
            return Response(
                {'error': 'Webhook endpoint not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not sig_header:
            return Response({'error': 'Missing Stripe-Signature header'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as exc:
            logger.warning('Invalid Stripe webhook payload: %s', exc)
            return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError as exc:
            logger.warning('Invalid Stripe webhook signature: %s', exc)
            return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

        event_dict = stripe_event_to_dict(event)
        event_id = event_dict.get('id')
        event_type = event_dict.get('type', 'unknown')

        if event_id and PaymentGatewayMixin.webhook_event_already_processed_stripe(event_id, None):
            return Response({'received': True, 'duplicate': True})

        webhook_event = WebhookEvent.objects.create(
            gateway='stripe',
            event_type=event_type,
            payload=event_dict,
        )

        try:
            StripeService.process_webhook(webhook_event)
        except Exception as exc:
            logger.exception('Stripe webhook processing failed')
            webhook_event.error_message = str(exc)[:2000]
            webhook_event.save(update_fields=['error_message'])
            return Response({'error': 'Processing failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save(update_fields=['processed', 'processed_at'])

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
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """Accept IPN, validate with SSLCommerz, update invoice/payment state."""
        if not settings.SSLCOMMERZ_STORE_ID or not settings.SSLCOMMERZ_STORE_PASSWORD:
            logger.error('SSLCommerz store credentials are not configured')
            return Response(
                {'error': 'Webhook endpoint not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload_dict = _flatten_drf_request_data(request)

        webhook_event = WebhookEvent.objects.create(
            gateway='sslcommerz',
            event_type='payment_notification',
            payload=payload_dict,
        )

        try:
            SSLCommerzService.process_ipn(webhook_event)
        except Exception as exc:
            logger.exception('SSLCommerz IPN processing failed')
            webhook_event.error_message = str(exc)[:2000]
            webhook_event.save(update_fields=['error_message'])
            # Return 200 so SSLCommerz does not retry indefinitely on bad data;
            # investigate via WebhookEvent.error_message.
            return Response({'status': 'failed', 'detail': str(exc)[:500]})

        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save(update_fields=['processed', 'processed_at'])

        return Response({'status': 'success'})
