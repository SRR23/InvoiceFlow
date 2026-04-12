"""
Payment gateway services for Stripe and SSLCommerz.
"""
import logging
from decimal import Decimal

import requests
import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.invoices.models import Invoice
from apps.payments.credential_resolution import (
    resolve_sslcommerz_credentials,
    resolve_stripe_secret_key,
)
from apps.payments.models import Payment
from apps.payments.payment_link_policy import (
    assert_may_create_payment_link,
    stripe_checkout_expires_at_unix,
)
from utils.constants import (
    INVOICE_STATUS_PAID,
    PAYMENT_GATEWAY_SSLCOMMERZ,
    PAYMENT_GATEWAY_STRIPE,
    PAYMENT_STATUS_COMPLETED,
    PAYMENT_STATUS_PENDING,
)

logger = logging.getLogger(__name__)


def _stripe_event_to_dict(event):
    """Serialize a Stripe Event to a plain dict for JSONField storage."""
    try:
        from stripe.util import convert_to_dict

        return convert_to_dict(event)
    except Exception:
        if hasattr(event, "to_dict"):
            return event.to_dict()
        return dict(event)


class PaymentGatewayMixin:
    """Shared helpers for recording gateway success and receipts."""

    @staticmethod
    def webhook_event_already_processed_stripe(stripe_event_id, current_webhook_pk):
        """True if another row already recorded this Stripe event as processed."""
        from apps.payments.models import WebhookEvent

        qs = WebhookEvent.objects.filter(
            gateway=PAYMENT_GATEWAY_STRIPE,
            payload__id=stripe_event_id,
            processed=True,
        )
        if current_webhook_pk:
            qs = qs.exclude(pk=current_webhook_pk)
        return qs.exists()

    @staticmethod
    @transaction.atomic
    def finalize_successful_payment(invoice, gateway, transaction_id, amount, currency, gateway_response):
        """
        Idempotently mark invoice paid and upsert a completed Payment row.

        Returns True when the invoice was not PAID before this call and is now PAID
        (caller may send receipt). Duplicate webhooks return False.
        """
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        was_unpaid = locked.status != INVOICE_STATUS_PAID

        payment, created = Payment.objects.get_or_create(
            transaction_id=transaction_id,
            defaults={
                "invoice": locked,
                "gateway": gateway,
                "amount": amount,
                "currency": currency,
                "status": PAYMENT_STATUS_COMPLETED,
                "paid_at": timezone.now(),
                "payment_url": "",
                "gateway_response": gateway_response or {},
            },
        )

        if payment.invoice_id != locked.id:
            raise ValueError("Transaction ID is already associated with a different invoice")

        if not created:
            payment.status = PAYMENT_STATUS_COMPLETED
            payment.paid_at = timezone.now()
            payment.gateway_response = gateway_response or {}
            payment.amount = amount
            payment.currency = currency
            payment.payment_url = ""
            payment.save()

        if was_unpaid:
            locked.status = INVOICE_STATUS_PAID
            locked.save(update_fields=["status"])
            return True
        return False

    @staticmethod
    def send_receipt_async(invoice_id, transaction_id_for_log):
        """Queue payment receipt email after successful charge (best-effort)."""
        try:
            payment = Payment.objects.filter(
                invoice_id=invoice_id,
                transaction_id=transaction_id_for_log,
            ).first()
            if not payment:
                return
            from apps.notifications.tasks import send_payment_receipt

            send_payment_receipt.delay(payment.id)
        except Exception as exc:
            logger.warning("Could not queue payment receipt: %s", exc)

    @staticmethod
    @transaction.atomic
    def upgrade_pending_ssl_to_completed(
        invoice,
        tran_id,
        val_id,
        amount,
        currency,
        gateway_response,
    ):
        """
        If we stored a pending Payment keyed by merchant ``tran_id``, re-key it to
        gateway ``val_id`` and mark completed. Otherwise return None so the caller
        can use ``finalize_successful_payment`` with ``val_id`` only.
        """
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        was_unpaid = locked.status != INVOICE_STATUS_PAID

        pending = Payment.objects.select_for_update().filter(
            invoice=invoice,
            gateway=PAYMENT_GATEWAY_SSLCOMMERZ,
            status=PAYMENT_STATUS_PENDING,
            transaction_id=str(tran_id),
        ).first()

        if not pending:
            return None

        conflict = Payment.objects.filter(transaction_id=val_id).exclude(pk=pending.pk).first()
        if conflict:
            if conflict.invoice_id == invoice.id and conflict.status == PAYMENT_STATUS_COMPLETED:
                return False
            raise ValueError("SSLCommerz val_id is already associated with another payment")

        pending.transaction_id = val_id
        pending.status = PAYMENT_STATUS_COMPLETED
        pending.paid_at = timezone.now()
        pending.amount = amount
        pending.currency = currency
        pending.gateway_response = gateway_response or {}
        pending.payment_url = ""
        pending.save()

        if was_unpaid:
            locked.status = INVOICE_STATUS_PAID
            locked.save(update_fields=["status"])
            return True
        return False


class StripeService:
    """Service for handling Stripe payments."""

    # Checkout Session events that indicate a successful payment for our integration.
    _CHECKOUT_SUCCESS_TYPES = frozenset(
        {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
        }
    )

    @staticmethod
    def create_checkout_session(invoice):
        """
        Create a Stripe checkout session for an invoice.
        Uses the invoice owner's Stripe secret key (merchant settings or platform default).
        Returns checkout URL and session id (session id is the gateway transaction reference).
        """
        secret_key = resolve_stripe_secret_key(invoice.user)
        if not secret_key:
            raise ValueError(
                "Stripe secret key is not configured for this account. "
                "Add it under Payment gateway settings (or set platform STRIPE_SECRET_KEY for dev)."
            )

        stripe.api_key = secret_key

        try:
            assert_may_create_payment_link(invoice)
            expires_at = stripe_checkout_expires_at_unix(invoice)
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": invoice.currency.lower(),
                            "product_data": {
                                "name": f"Invoice {invoice.invoice_number}",
                            },
                            "unit_amount": int(invoice.total_amount * 100),  # Convert to cents
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                expires_at=expires_at,
                success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
                metadata={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "user_id": str(invoice.user_id),
                },
            )

            return {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
            }
        except Exception as e:
            # Log error
            raise Exception(f"Stripe checkout session creation failed: {str(e)}") from e

    @staticmethod
    def process_webhook(webhook_event, merchant_user_id=None):
        """
        Process a Stripe webhook event stored on ``WebhookEvent`` (payload = full Stripe event dict).
        Updates invoice and payment status for successful Checkout sessions.
        """
        payload = webhook_event.payload
        event_type = payload.get("type")
        event_id = payload.get("id")

        if not event_id:
            raise ValueError("Stripe event missing id")

        # Idempotency: another worker may have already processed this Stripe event id.
        prior_done = PaymentGatewayMixin.webhook_event_already_processed_stripe(
            event_id, webhook_event.pk
        )
        if prior_done:
            logger.info("Skipping already-processed Stripe event %s", event_id)
            return

        if event_type in StripeService._CHECKOUT_SUCCESS_TYPES:
            session = payload.get("data", {}).get("object") or {}
            StripeService._handle_checkout_session_success(session, merchant_user_id=merchant_user_id)
            return

        # Other event types are acknowledged without action (subscription, etc.).
        logger.debug("Stripe webhook type %s ignored (no handler)", event_type)

    @staticmethod
    def _handle_checkout_session_success(session, merchant_user_id=None):
        """Apply a paid Checkout Session to the invoice referenced in metadata."""
        metadata = session.get("metadata") or {}
        invoice_id_raw = metadata.get("invoice_id")
        if not invoice_id_raw:
            raise ValueError("checkout.session missing metadata.invoice_id")

        try:
            invoice_id = int(invoice_id_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid metadata.invoice_id") from exc

        meta_user_raw = metadata.get("user_id")
        if merchant_user_id is not None and meta_user_raw:
            try:
                meta_user_id = int(meta_user_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid metadata.user_id") from exc
            if meta_user_id != merchant_user_id:
                raise ValueError("metadata.user_id does not match webhook merchant")

        payment_status = (session.get("payment_status") or "").lower()
        if payment_status != "paid":
            logger.info(
                "Checkout session %s payment_status=%s — skipping mark paid",
                session.get("id"),
                payment_status,
            )
            return

        session_id = session.get("id")
        if not session_id:
            raise ValueError("checkout.session missing id")

        amount_total = session.get("amount_total")
        currency = (session.get("currency") or "usd").upper()

        invoice = Invoice.objects.filter(pk=invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice id={invoice_id} not found")

        if merchant_user_id is not None and invoice.user_id != merchant_user_id:
            raise ValueError("Invoice does not belong to the webhook merchant account")

        if invoice.currency.upper() != currency:
            raise ValueError(
                f"Currency mismatch: invoice {invoice.currency} vs session {currency}"
            )

        # amount_total is in smallest currency unit (e.g. cents).
        if amount_total is None:
            raise ValueError("checkout.session missing amount_total")
        paid_decimal = Decimal(amount_total) / Decimal(100)
        if abs(paid_decimal - invoice.total_amount) > Decimal("0.01"):
            raise ValueError(
                f"Amount mismatch: invoice {invoice.total_amount} vs session {paid_decimal}"
            )

        receipt_send = PaymentGatewayMixin.finalize_successful_payment(
            invoice=invoice,
            gateway=PAYMENT_GATEWAY_STRIPE,
            transaction_id=session_id,
            amount=paid_decimal,
            currency=currency,
            gateway_response=session,
        )
        if receipt_send:
            PaymentGatewayMixin.send_receipt_async(invoice.id, session_id)


class SSLCommerzService:
    """Service for handling SSLCommerz payments."""

    @staticmethod
    def _api_base(is_live: bool) -> str:
        if is_live:
            return "https://securepay.sslcommerz.com"
        return "https://sandbox.sslcommerz.com"

    @staticmethod
    def _parse_hosted_session_json(response):
        """
        Parse JSON from ``gwprocess/v4/api.php``.

        Success payloads typically include ``status`` (SUCCESS), ``GatewayPageURL``,
        and ``sessionkey``. Failures set ``status`` to FAILED and ``failedreason``.
        """
        try:
            data = response.json()
        except ValueError as exc:
            snippet = (response.text or "")[:500]
            raise ValueError(
                f"SSLCommerz returned non-JSON body (HTTP {response.status_code}): {snippet!r}"
            ) from exc

        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            raise ValueError("SSLCommerz session response has unexpected shape")

        return data

    @staticmethod
    def create_payment_session(invoice):
        """
        Create an SSLCommerz hosted payment session for an invoice.

        Returns a dict safe to send to the frontend: ``redirect_url`` (GatewayPageURL),
        ``tran_id``, and optional ``session_key``. Store credentials are never included.
        """

        assert_may_create_payment_link(invoice)

        store_id, store_password, is_live = resolve_sslcommerz_credentials(invoice.user)
        if not store_id or not store_password:
            raise ValueError(
                "SSLCommerz store credentials are not configured for this account. "
                "Add them under Payment gateway settings (or set platform SSLCOMMERZ_* for dev)."
            )
        api_url = SSLCommerzService._api_base(is_live)

        tran_id = f"INV-{invoice.id}-{invoice.public_id.hex[:8]}"

        # Request body for SSLCommerz Hosted Payment / session API (v4).
        payment_data = {
            "store_id": store_id,
            "store_passwd": store_password,
            "total_amount": str(invoice.total_amount),
            "currency": invoice.currency,
            "tran_id": tran_id,
            "success_url": f"{settings.FRONTEND_URL}/payment/success",
            "fail_url": f"{settings.FRONTEND_URL}/payment/fail",
            "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel",
            "emi_option": 0,
            "cus_name": invoice.client.name,
            "cus_email": invoice.client.email or "",
            "cus_phone": invoice.client.phone or "",
            "product_name": f"Invoice {invoice.invoice_number}",
            "product_category": "Invoice",
            "product_profile": "general",
        }

        try:
            response = requests.post(
                f"{api_url}/gwprocess/v4/api.php",
                data=payment_data,
                timeout=60,
            )

            body = SSLCommerzService._parse_hosted_session_json(response)

            if response.status_code != 200:
                reason = (
                    body.get("failedreason")
                    or body.get("message")
                    or (response.text or "")[:300]
                )
                raise ValueError(f"SSLCommerz HTTP {response.status_code}: {reason}")

            status_raw = (body.get("status") or "").strip().upper()
            # Documented success is status=SUCCESS; some responses omit status but include GatewayPageURL.
            if status_raw == "FAILED":
                reason = (
                    body.get("failedreason")
                    or body.get("failed_reason")
                    or body.get("error")
                    or body.get("message")
                    or "session initiation failed"
                )
                raise ValueError(f"SSLCommerz session failed: {reason}")

            gateway_url = (body.get("GatewayPageURL") or body.get("gateway_page_url") or "").strip()
            if not gateway_url:
                reason = (
                    body.get("failedreason")
                    or body.get("failed_reason")
                    or "missing GatewayPageURL"
                )
                raise ValueError(f"SSLCommerz session failed ({status_raw or 'UNKNOWN'}): {reason}")

            session_key = body.get("sessionkey") or body.get("session_key")

            return {
                "redirect_url": gateway_url,
                "tran_id": tran_id,
                "session_key": session_key,
                "invoice_id": invoice.id,
            }
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"SSLCommerz payment session creation failed: {str(e)}") from e

    @staticmethod
    def validate_transaction(val_id, store_id, store_passwd, is_live):
        """
        Call SSLCommerz validation API to confirm ``val_id`` after IPN.
        Returns the parsed validation payload (dict).
        """
        if not val_id:
            raise ValueError("val_id is required")
        if not store_id or not store_passwd:
            raise ValueError("SSLCommerz store credentials are required for validation")
        base = SSLCommerzService._api_base(is_live)
        url = f"{base}/validator/api/validationserverAPI.php"
        params = {
            "val_id": val_id,
            "store_id": store_id,
            "store_passwd": store_passwd,
            "format": "json",
            "v": "1",
        }
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            raise ValueError("Unexpected validation response shape")

        status = (data.get("status") or "").strip().upper()
        if status != "VALID":
            raise ValueError(f"SSLCommerz validation status is not VALID: {status!r}")

        return data

    @staticmethod
    def parse_invoice_id_from_tran_id(tran_id):
        """
        Parse invoice PK from our ``tran_id`` format: INV-<id>-<suffix>.
        """
        if not tran_id:
            return None
        parts = str(tran_id).split("-")
        if len(parts) < 3 or parts[0].upper() != "INV":
            return None
        try:
            return int(parts[1])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def process_ipn(
        webhook_event,
        *,
        store_id=None,
        store_passwd=None,
        is_live=None,
        merchant_user_id=None,
    ):
        """
        Process an SSLCommerz IPN (Instant Payment Notification).
        Verifies ``val_id`` server-side, then updates invoice and payment status.

        For merchant-specific webhooks, pass ``store_id``, ``store_passwd``, ``is_live``,
        and ``merchant_user_id``. For legacy single-tenant IPN, omit these to use
        platform settings from Django settings (``SSLCOMMERZ_*``).
        """
        payload = webhook_event.payload
        if not isinstance(payload, dict):
            raise ValueError("IPN payload must be a dict")

        if store_id is None:
            store_id = getattr(settings, "SSLCOMMERZ_STORE_ID", "") or ""
            store_passwd = getattr(settings, "SSLCOMMERZ_STORE_PASSWORD", "") or ""
            is_live = bool(getattr(settings, "SSLCOMMERZ_IS_LIVE", False))

        val_id = payload.get("val_id") or payload.get("valId")
        tran_id = payload.get("tran_id") or payload.get("tranId")

        if not val_id:
            raise ValueError("IPN missing val_id")

        if not store_id or not store_passwd:
            raise ValueError("SSLCommerz store credentials are not configured")

        # Idempotency: same val_id already completed.
        if Payment.objects.filter(
            gateway=PAYMENT_GATEWAY_SSLCOMMERZ,
            transaction_id=val_id,
            status=PAYMENT_STATUS_COMPLETED,
        ).exists():
            logger.info("SSLCommerz IPN duplicate for val_id=%s — skipping", val_id)
            return

        validated = SSLCommerzService.validate_transaction(val_id, store_id, store_passwd, is_live)

        validated_tran = validated.get("tran_id") or tran_id
        if tran_id and validated_tran and str(validated_tran) != str(tran_id):
            raise ValueError("tran_id mismatch between IPN and validation response")

        invoice_id = SSLCommerzService.parse_invoice_id_from_tran_id(validated_tran)
        if not invoice_id:
            raise ValueError(f"Could not parse invoice from tran_id={validated_tran!r}")

        invoice = Invoice.objects.filter(pk=invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice id={invoice_id} not found")

        if merchant_user_id is not None and invoice.user_id != merchant_user_id:
            raise ValueError("Invoice does not belong to this merchant account")

        amount_raw = (
            validated.get("amount")
            or validated.get("store_amount")
            or validated.get("currency_amount")
        )
        if amount_raw is None:
            raise ValueError("Validation response missing amount")
        paid_decimal = Decimal(str(amount_raw))
        currency = (validated.get("currency") or invoice.currency or "BDT").upper()

        if invoice.currency.upper() != currency:
            raise ValueError(
                f"Currency mismatch: invoice {invoice.currency} vs gateway {currency}"
            )

        if abs(paid_decimal - invoice.total_amount) > Decimal("0.01"):
            raise ValueError(
                f"Amount mismatch: invoice {invoice.total_amount} vs gateway {paid_decimal}"
            )

        gw_payload = {"ipn": payload, "validated": validated}
        merged = PaymentGatewayMixin.upgrade_pending_ssl_to_completed(
            invoice=invoice,
            tran_id=str(validated_tran),
            val_id=str(val_id),
            amount=paid_decimal,
            currency=currency,
            gateway_response=gw_payload,
        )
        if merged is not None:
            if merged:
                PaymentGatewayMixin.send_receipt_async(invoice.id, val_id)
            return

        receipt_send = PaymentGatewayMixin.finalize_successful_payment(
            invoice=invoice,
            gateway=PAYMENT_GATEWAY_SSLCOMMERZ,
            transaction_id=val_id,
            amount=paid_decimal,
            currency=currency,
            gateway_response=gw_payload,
        )
        if receipt_send:
            PaymentGatewayMixin.send_receipt_async(invoice.id, val_id)


# Export for Stripe webhook view
stripe_event_to_dict = _stripe_event_to_dict
