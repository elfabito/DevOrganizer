"""
Stripe Integration Service for DevOrganizer
Handles subscription creation, management, and webhook events
"""
import os
import stripe
from typing import Dict, Optional
from flask import current_app
from datetime import datetime, timezone

# Initialize Stripe with secret key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')


def get_stripe_config() -> Dict:
    """Get Stripe configuration from environment"""
    return {
        'publishable_key': os.getenv('STRIPE_PUBLISHABLE_KEY'),
        'secret_key': os.getenv('STRIPE_SECRET_KEY'),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET'),
        'price_id_pro': os.getenv('STRIPE_PRICE_ID_PRO')
    }


def create_checkout_session(user_id: str, email: str, plan: str = 'pro') -> Dict:
    """
    Create a Stripe Checkout Session for subscription

    Args:
        user_id: The user's ID
        email: The user's email address
        plan: The plan type ('pro')

    Returns:
        Dictionary with session_id and checkout_url
    """
    try:
        config = get_stripe_config()

        if not config['price_id_pro']:
            raise ValueError("STRIPE_PRICE_ID_PRO not configured in environment")

        # Determine success and cancel URLs based on environment
        if current_app.config['ENV'] == 'production':
            # Use your Render domain
            base_url = os.getenv('APP_URL', 'https://your-app.onrender.com')
        else:
            base_url = 'http://127.0.0.1:5000'

        success_url = f"{base_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/subscription/cancel"

        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            customer_email=email,
            client_reference_id=user_id,
            payment_method_types=['card'],
            line_items=[{
                'price': config['price_id_pro'],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                'trial_period_days': 30,
                'metadata': {
                    'user_id': user_id,
                    'plan': plan
                }
            },
            metadata={
                'user_id': user_id,
                'plan': plan
            }
        )

        return {
            'session_id': session.id,
            'checkout_url': session.url
        }

    except Exception as e:
        current_app.logger.error(f"Error creating checkout session: {str(e)}")
        raise


def create_customer_portal_session(customer_id: str) -> Dict:
    """
    Create a Stripe Customer Portal Session for subscription management

    Args:
        customer_id: The Stripe customer ID

    Returns:
        Dictionary with portal_url
    """
    try:
        # Determine return URL based on environment
        if current_app.config['ENV'] == 'production':
            return_url = os.getenv('APP_URL', 'https://your-app.onrender.com')
        else:
            return_url = 'http://127.0.0.1:5000'

        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )

        return {
            'portal_url': session.url
        }

    except Exception as e:
        current_app.logger.error(f"Error creating portal session: {str(e)}")
        raise


def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> bool:
    """
    Cancel a Stripe subscription

    Args:
        subscription_id: The Stripe subscription ID
        at_period_end: If True, cancel at end of billing period. If False, cancel immediately.

    Returns:
        True if successful
    """
    try:
        if at_period_end:
            # Cancel at end of billing period (recommended)
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        else:
            # Cancel immediately
            stripe.Subscription.delete(subscription_id)

        return True

    except Exception as e:
        current_app.logger.error(f"Error canceling subscription: {str(e)}")
        raise


def handle_webhook_event(payload: bytes, sig_header: str) -> Optional[Dict]:
    """
    Handle Stripe webhook events

    Args:
        payload: The raw request body
        sig_header: The Stripe-Signature header

    Returns:
        Dictionary with event details to process, or None if event is not relevant
    """
    config = get_stripe_config()
    webhook_secret = config['webhook_secret']

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )

        event_type = event['type']
        event_data = event['data']['object']

        current_app.logger.info(f"Received Stripe webhook: {event_type}")

        # Handle different event types
        if event_type == 'checkout.session.completed':
            # Payment successful, subscription created
            return {
                'event_type': 'checkout_completed',
                'user_id': event_data.get('client_reference_id') or event_data.get('metadata', {}).get('user_id'),
                'customer_id': event_data.get('customer'),
                'subscription_id': event_data.get('subscription'),
                'email': event_data.get('customer_email')
            }

        elif event_type == 'customer.subscription.created':
            # Subscription created (may be in trial)
            return {
                'event_type': 'subscription_created',
                'user_id': event_data.get('metadata', {}).get('user_id'),
                'customer_id': event_data.get('customer'),
                'subscription_id': event_data['id'],
                'status': event_data['status'],
                'trial_end': event_data.get('trial_end'),
                'current_period_end': event_data['current_period_end']
            }

        elif event_type == 'customer.subscription.updated':
            # Subscription updated (e.g., trial ended, plan changed)
            return {
                'event_type': 'subscription_updated',
                'user_id': event_data.get('metadata', {}).get('user_id'),
                'customer_id': event_data.get('customer'),
                'subscription_id': event_data['id'],
                'status': event_data['status'],
                'trial_end': event_data.get('trial_end'),
                'current_period_end': event_data['current_period_end'],
                'cancel_at_period_end': event_data.get('cancel_at_period_end', False)
            }

        elif event_type == 'customer.subscription.deleted':
            # Subscription canceled
            return {
                'event_type': 'subscription_deleted',
                'user_id': event_data.get('metadata', {}).get('user_id'),
                'customer_id': event_data.get('customer'),
                'subscription_id': event_data['id'],
                'status': 'canceled'
            }

        elif event_type == 'invoice.payment_succeeded':
            # Payment succeeded
            return {
                'event_type': 'payment_succeeded',
                'customer_id': event_data.get('customer'),
                'subscription_id': event_data.get('subscription'),
                'amount_paid': event_data.get('amount_paid'),
                'currency': event_data.get('currency')
            }

        elif event_type == 'invoice.payment_failed':
            # Payment failed
            return {
                'event_type': 'payment_failed',
                'user_id': event_data.get('metadata', {}).get('user_id'),
                'customer_id': event_data.get('customer'),
                'subscription_id': event_data.get('subscription')
            }

        else:
            # Event type not handled
            current_app.logger.info(f"Unhandled webhook event type: {event_type}")
            return None

    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error(f"Webhook signature verification failed: {str(e)}")
        raise
    except Exception as e:
        current_app.logger.error(f"Error handling webhook: {str(e)}")
        raise


def get_subscription_details(subscription_id: str) -> Optional[Dict]:
    """
    Get details of a Stripe subscription

    Args:
        subscription_id: The Stripe subscription ID

    Returns:
        Dictionary with subscription details
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)

        return {
            'id': subscription.id,
            'status': subscription.status,
            'customer': subscription.customer,
            'current_period_start': subscription.current_period_start,
            'current_period_end': subscription.current_period_end,
            'trial_end': subscription.trial_end,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'canceled_at': subscription.canceled_at
        }

    except Exception as e:
        current_app.logger.error(f"Error getting subscription details: {str(e)}")
        return None


def get_customer_by_email(email: str) -> Optional[Dict]:
    """
    Get Stripe customer by email

    Args:
        email: Customer email

    Returns:
        Customer data or None
    """
    try:
        customers = stripe.Customer.list(email=email, limit=1)

        if customers.data:
            customer = customers.data[0]
            return {
                'id': customer.id,
                'email': customer.email,
                'subscriptions': customer.subscriptions.data if customer.subscriptions else []
            }

        return None

    except Exception as e:
        current_app.logger.error(f"Error getting customer by email: {str(e)}")
        return None
