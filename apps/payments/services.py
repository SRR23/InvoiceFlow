"""
Payment gateway services for Stripe and SSLCommerz.
"""
from django.conf import settings
from decimal import Decimal


class StripeService:
    """Service for handling Stripe payments."""
    
    @staticmethod
    def create_checkout_session(invoice):
        """
        Create a Stripe checkout session for an invoice.
        Returns the checkout URL.
        """
        import stripe
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': invoice.currency.lower(),
                        'product_data': {
                            'name': f'Invoice {invoice.invoice_number}',
                        },
                        'unit_amount': int(invoice.total_amount * 100),  # Convert to cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
                metadata={
                    'invoice_id': str(invoice.id),
                    'invoice_number': invoice.invoice_number,
                }
            )
            
            return checkout_session.url
        except Exception as e:
            # Log error
            raise Exception(f"Stripe checkout session creation failed: {str(e)}")
    
    @staticmethod
    def process_webhook(webhook_event):
        """
        Process a Stripe webhook event.
        Updates invoice and payment status.
        """
        # TODO: Implement webhook processing
        pass


class SSLCommerzService:
    """Service for handling SSLCommerz payments."""
    
    @staticmethod
    def create_payment_session(invoice):
        """
        Create an SSLCommerz payment session for an invoice.
        Returns payment data including redirect URL.
        """
        import requests
        
        store_id = settings.SSLCOMMERZ_STORE_ID
        store_password = settings.SSLCOMMERZ_STORE_PASSWORD
        is_live = settings.SSLCOMMERZ_IS_LIVE
        
        # Determine API URL based on live/sandbox mode
        if is_live:
            api_url = 'https://securepay.sslcommerz.com'
        else:
            api_url = 'https://sandbox.sslcommerz.com'
        
        # Prepare payment data
        payment_data = {
            'store_id': store_id,
            'store_passwd': store_password,
            'total_amount': str(invoice.total_amount),
            'currency': invoice.currency,
            'tran_id': f"INV-{invoice.id}-{invoice.public_id.hex[:8]}",
            'success_url': f"{settings.FRONTEND_URL}/payment/success",
            'fail_url': f"{settings.FRONTEND_URL}/payment/fail",
            'cancel_url': f"{settings.FRONTEND_URL}/payment/cancel",
            'emi_option': 0,
            'cus_name': invoice.client.name,
            'cus_email': invoice.client.email or '',
            'cus_phone': invoice.client.phone or '',
            'product_name': f'Invoice {invoice.invoice_number}',
            'product_category': 'Invoice',
            'product_profile': 'general',
        }
        
        try:
            response = requests.post(
                f"{api_url}/gwprocess/v4/api.php",
                data=payment_data
            )
            
            if response.status_code == 200:
                # Parse response
                # SSLCommerz returns form data or JSON
                return {
                    'redirect_url': response.url if hasattr(response, 'url') else None,
                    'payment_data': payment_data
                }
            else:
                raise Exception(f"SSLCommerz API error: {response.status_code}")
        except Exception as e:
            raise Exception(f"SSLCommerz payment session creation failed: {str(e)}")
    
    @staticmethod
    def process_ipn(webhook_event):
        """
        Process an SSLCommerz IPN (Instant Payment Notification).
        Verifies and updates invoice and payment status.
        """
        # TODO: Implement IPN processing
        pass
