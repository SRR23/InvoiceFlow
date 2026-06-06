import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from utils.constants import SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_TRIALING

from .serializers import (
    SubscriptionCheckoutRequestSerializer,
    SubscriptionCheckoutResponseSerializer,
    SubscriptionStatusSerializer,
)
from .services import create_subscription_checkout_session

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Subscription'],
    summary='SaaS subscription status',
    description=(
        'Trial end time, Stripe subscription status, and whether business features are '
        'currently allowed. Always available when authenticated (used to show paywall UI).'
    ),
    responses={200: SubscriptionStatusSerializer},
)
class SubscriptionStatusView(APIView):
    """Expose subscription / trial flags for the current user (no business subscription gate)."""

    # Intentionally not IsBusinessUser: paywall UI must work when trial/subscription blocks other APIs.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        payload = {
            'trial_ends_at': user.trial_ends_at,
            'subscription_status': user.subscription_status,
            'has_active_app_access': user.has_active_app_access(),
        }
        return Response(SubscriptionStatusSerializer(payload).data)


@extend_schema(
    tags=['Subscription'],
    summary='Start Stripe subscription checkout',
    description=(
        'Creates a Stripe Checkout Session (``mode=subscription``) with **dynamic** ``price_data`` '
        'from an active ``SubscriptionPackage`` (optional JSON body ``package_code``). '
        'Uses **platform** ``STRIPE_SECRET_KEY``. Configure the **platform** webhook URL in Stripe '
        'for ``checkout.session.completed`` and ``customer.subscription.*`` events.'
    ),
    request=SubscriptionCheckoutRequestSerializer,
    responses={
        200: SubscriptionCheckoutResponseSerializer,
        400: OpenApiResponse(description='Already subscribed or validation error'),
        503: OpenApiResponse(description='Stripe not configured'),
    },
)
class SubscriptionCheckoutView(APIView):
    """Stripe-hosted monthly subscription — no cancel/downgrade APIs (managed in Stripe if needed)."""

    # Intentionally not IsBusinessUser: users without access must still start Checkout.
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user: User = request.user
        if not user.is_business_user:
            return Response(
                {'detail': 'Subscriptions apply to business accounts only.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        on_trial = user.trial_ends_at and now < user.trial_ends_at
        paid_like = user.subscription_status in (SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_TRIALING)
        if user.stripe_subscription_id and paid_like and not on_trial:
            return Response(
                {'detail': 'You already have an active subscription.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Match legacy behavior: JSON may send ``package_code`` as a non-string (e.g. numeric code).
        request_data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        raw_code = request_data.get('package_code')
        if raw_code is not None and not isinstance(raw_code, str):
            request_data['package_code'] = str(raw_code)

        body_serializer = SubscriptionCheckoutRequestSerializer(data=request_data)
        body_serializer.is_valid(raise_exception=True)
        package_code = body_serializer.validated_data.get('package_code')
        if package_code is not None:
            package_code = str(package_code).strip() or None

        try:
            payload = create_subscription_checkout_session(user, package_code=package_code)
        except ValueError as exc:
            msg = str(exc)
            code = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if 'not configured' in msg.lower() or 'not available' in msg.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': msg}, status=code)
        except Exception:
            logger.exception('Subscription checkout session failed')
            return Response(
                {'detail': 'Unable to start checkout. Try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        out = SubscriptionCheckoutResponseSerializer(payload)
        return Response(out.data, status=status.HTTP_200_OK)
