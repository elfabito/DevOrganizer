"""
Subscription Routes for DevOrganizer
Add these routes to app.py
"""

# Import statements to add at the top of app.py:
"""
from stripe_service import (
    create_checkout_session,
    create_customer_portal_session,
    handle_webhook_event,
    get_stripe_config
)
from subscription_limits import (
    check_resource_limit,
    require_plan,
    get_user_plan_limits,
    can_use_clickup
)
"""

# Routes to add to app.py:

"""
# ============================================================================
# SUBSCRIPTION ROUTES
# ============================================================================

@app.route('/home')
def landing_page():
    '''Landing page for non-authenticated users'''
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('index'))

    return render_template('landing.html')


@app.route('/create-checkout-session', methods=['POST', 'GET'])
@login_required
def create_stripe_checkout():
    '''Create a Stripe Checkout Session for Pro subscription'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user info
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Check if user already has Pro
        if user.get('plan_type') == 'pro':
            subscription_status = user.get('subscription_status')
            if subscription_status in ['trialing', 'active']:
                return jsonify({
                    'error': 'You already have an active Pro subscription',
                    'redirect': url_for('index')
                }), 400

        # Create Stripe Checkout Session
        session_data = create_checkout_session(
            user_id=user_id,
            email=user['email'],
            plan='pro'
        )

        # For GET requests, redirect to Stripe Checkout
        if request.method == 'GET':
            return redirect(session_data['checkout_url'])

        # For POST requests (AJAX), return JSON
        return jsonify(session_data)

    except Exception as e:
        current_app.logger.error(f'Error creating checkout session: {str(e)}', exc_info=True)
        if request.method == 'GET':
            flash('Failed to create checkout session. Please try again.', 'error')
            return redirect(url_for('index'))
        return jsonify({'error': str(e)}), 500


@app.route('/create-portal-session', methods=['POST', 'GET'])
@login_required
@require_plan('pro')
def create_stripe_portal():
    '''Create a Stripe Customer Portal Session for subscription management'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user info
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get Stripe customer ID
        customer_id = user.get('stripe_customer_id')
        if not customer_id:
            return jsonify({'error': 'No active subscription found'}), 400

        # Create portal session
        portal_data = create_customer_portal_session(customer_id)

        # For GET requests, redirect to portal
        if request.method == 'GET':
            return redirect(portal_data['portal_url'])

        # For POST requests, return JSON
        return jsonify(portal_data)

    except Exception as e:
        current_app.logger.error(f'Error creating portal session: {str(e)}', exc_info=True)
        if request.method == 'GET':
            flash('Failed to open subscription portal. Please try again.', 'error')
            return redirect(url_for('index'))
        return jsonify({'error': str(e)}), 500


@app.route('/subscription/success')
@login_required
def subscription_success():
    '''Success page after successful subscription'''
    return render_template('subscription_success.html')


@app.route('/subscription/cancel')
def subscription_cancel():
    '''Cancel page when user cancels subscription checkout'''
    return render_template('subscription_cancel.html')


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    '''Handle Stripe webhook events'''
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Process the webhook event
        event_data = handle_webhook_event(payload, sig_header)

        if not event_data:
            # Event not handled
            return jsonify({'status': 'ignored'}), 200

        event_type = event_data['event_type']
        current_app.logger.info(f'Processing webhook: {event_type}')

        # Handle checkout completion
        if event_type == 'checkout_completed':
            user_id = event_data.get('user_id')
            customer_id = event_data.get('customer_id')
            subscription_id = event_data.get('subscription_id')

            if user_id and customer_id:
                # Update user with Stripe customer and subscription IDs
                user_storage.update_user_subscription(
                    user_id,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    plan_type='pro',
                    subscription_status='trialing'
                )
                current_app.logger.info(f'User {user_id} upgraded to Pro (trial)')

        # Handle subscription creation
        elif event_type == 'subscription_created':
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    subscription_status=event_data.get('status'),
                    trial_end=event_data.get('trial_end'),
                    subscription_current_period_end=event_data.get('current_period_end')
                )

        # Handle subscription updates (e.g., trial ending, plan changes)
        elif event_type == 'subscription_updated':
            customer_id = event_data.get('customer_id')

            # Find user by customer_id
            # Note: This requires iterating through users or having a reverse index
            # For now, we'll skip if user_id is not in metadata
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    subscription_status=event_data.get('status'),
                    trial_end=event_data.get('trial_end'),
                    subscription_current_period_end=event_data.get('current_period_end')
                )

        # Handle subscription deletion/cancellation
        elif event_type == 'subscription_deleted':
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    plan_type='free',
                    subscription_status='canceled',
                    stripe_subscription_id=None
                )
                current_app.logger.info(f'User {user_id} downgraded to Free')

        # Handle successful payments
        elif event_type == 'payment_succeeded':
            current_app.logger.info(f'Payment succeeded for subscription {event_data.get("subscription_id")}')

        # Handle failed payments
        elif event_type == 'payment_failed':
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    subscription_status='past_due'
                )
                current_app.logger.warning(f'Payment failed for user {user_id}')

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        current_app.logger.error(f'Webhook error: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 400


@app.route('/api/user/subscription', methods=['GET'])
@login_required
def get_user_subscription_info():
    '''Get current user's subscription information'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        subscription = user_storage.get_user_subscription(user_id)
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404

        return jsonify(subscription)

    except Exception as e:
        current_app.logger.error(f'Error getting subscription: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/usage', methods=['GET'])
@login_required
def get_user_usage():
    '''Get current user's usage statistics and limits'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user's plan
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        plan_type = user.get('plan_type', 'free')

        # Get usage counts
        usage = user_storage.get_user_usage_counts(user_id)

        # Get plan limits
        limits = get_user_plan_limits(plan_type)

        return jsonify({
            'plan_type': plan_type,
            'usage': usage,
            'limits': limits,
            'subscription_status': user.get('subscription_status')
        })

    except Exception as e:
        current_app.logger.error(f'Error getting usage: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/stripe/config', methods=['GET'])
@login_required
def get_stripe_public_config():
    '''Get Stripe publishable key for client-side'''
    try:
        config = get_stripe_config()
        return jsonify({
            'publishable_key': config['publishable_key']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# CSRF EXEMPTIONS FOR SUBSCRIPTION ROUTES
# ============================================================================

# Add these to the existing CSRF exemptions section:
csrf.exempt(stripe_webhook)
csrf.exempt(get_user_subscription_info)
csrf.exempt(get_user_usage)

"""
