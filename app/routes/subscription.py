from datetime import datetime, timedelta, timezone
import os
from flask import Blueprint, current_app, jsonify, render_template, request, flash, redirect, session, url_for, abort
from flask_login import current_user, login_required
import stripe
from app.forms import SubscriptionActionForm
from app.utils.stripe_helpers import handle_invoice_paid, handle_subscription_deleted, handle_subscription_updated
from app.models import User
from app.extensions import db
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
bp = Blueprint('subscription', __name__, url_prefix='/subscription')


@bp.route('/buy_subscription', methods=['GET', 'POST'])
def buy_subscription():
    form = SubscriptionActionForm()
    return render_template('subscription/buy_subscription.html', form=form)

#**********
# Stripe Integration
#**********

@bp.before_request
def configure_stripe():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

@bp.route('/stripe-webhook', methods=['POST'])
@csrf.exempt  # Add this decorator
def stripe_webhook():
    print("Stripe webhook called")
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle specific events
    if event['type'] == 'invoice.paid':
        handle_invoice_paid(event)
    elif event['type'] == 'customer.subscription.updated':
        handle_subscription_updated(event)
    elif event['type'] == 'customer.subscription.deleted':
        print("Subscription deleted event received")
        handle_subscription_deleted(event)
    
    return jsonify({'status': 'success'}), 200

@bp.route('/create_checkout_session', methods=['POST'])
@login_required
def create_checkout_session():
    """
    Creates a Stripe Checkout Session and redirects user to Stripe's payment page
    Flow:
    1. Validate price ID from request
    2. Create or retrieve Stripe customer
    3. Create Checkout Session
    4. Redirect to Stripe-hosted payment page
    """
    try:
        current_app.logger.info("Create checkout session called")  # Add this
        print("Creating checkout session")
        # 1. Validate Inputs
        price_id = request.form.get('price_id')
        tier = request.form.get('tier', 'individual')
        
        if not price_id or price_id != current_app.config['STRIPE_PRICE_INDIVIDUAL']:
            flash('Invalid subscription plan', 'danger')
            return redirect(url_for('subscription.buy_subscription'))

        # 2. Ensure Customer Exists
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={'user_id': current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()

        # 3. Create Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('subscription.payment_success', _external=True),
            cancel_url=url_for('subscription.payment_cancel', _external=True),
            customer=current_user.stripe_customer_id,
            subscription_data={
                'metadata': {
                    'user_id': current_user.id,
                    'tier': tier
                }
            }
        )

        # 4. Redirect to Stripe
        return redirect(session.url)

    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        flash('Payment processing error. Please try again.', 'danger')
        return redirect(url_for('subscription.buy_subscription'))
        
    except Exception as e:
        current_app.logger.critical(f"System error: {str(e)}")
        flash('An unexpected error occurred. Contact support.', 'danger')
        return redirect(url_for('main.index'))

@bp.route('/cancel_subscription', methods=['POST'])
@login_required
@csrf.exempt
def cancel_subscription():
    try:
        cancel_subscription_logic(current_user)
        flash('Subscription will cancel at period end', 'info')
    except ValueError as e:
        flash(str(e), 'warning')
    return redirect(url_for('subscription.buy_subscription'))

@bp.route('/resume_subscription', methods=['POST'])
@login_required
def resume_subscription():
    try:
        resume_subscription_logic(current_user)
        flash('Subscription resumed', 'success')
    except ValueError as e:
        flash(str(e), 'warning')
    return redirect(url_for('subscription.buy_subscription'))

@bp.route('/change-plan', methods=['POST'])
@login_required
def change_plan():
    new_price_id = request.form.get('price_id')
    
    # Get current subscription
    subscriptions = stripe.Subscription.list(
        customer=current_user.stripe_customer_id,
        status='active'
    )
    
    if not subscriptions.data:
        flash('No active subscription', 'warning')
        return redirect(url_for('subscription.manage'))
    
    # Update subscription
    stripe.Subscription.modify(
        subscriptions.data[0].id,
        items=[{
            'id': subscriptions.data[0].items.data[0].id,
            'price': new_price_id
        }],
        proration_behavior='always_invoice'
    )
    
    flash('Plan updated successfully', 'success')
    return redirect(url_for('subscription.manage'))

@bp.route('/payment/success')
def payment_success():
    return render_template('subscription/payment_success.html')

@bp.route('/payment/cancel')
def payment_cancel():
    return render_template('subscription/payment_cancel.html')


#**********
# Helper functions
#**********

def cancel_subscription_logic(user):
    """Business logic for subscription cancellation"""
    user.cancellation_requested = True
    user.subscription_status = 'pending_cancellation'
    user.requested_change = {'new_tier': 'free', 'when': 'now'}
    db.session.commit()

    subscriptions = stripe.Subscription.list(
        customer=user.stripe_customer_id,
        status='active'
    )
    
    if not subscriptions.data:
        raise ValueError("No active subscription")
    
    stripe.Subscription.modify(
        subscriptions.data[0].id,
        cancel_at_period_end=True
    )

def resume_subscription_logic(user):
    """Business logic for subscription resumption"""
    user.cancellation_requested = False
    user.subscription_status = 'active'
    user.requested_change = None
    db.session.commit()

    subscriptions = stripe.Subscription.list(
        customer=user.stripe_customer_id,
        status='active'
    )
    
    if not subscriptions.data:
        raise ValueError("No active subscription")
    
    stripe.Subscription.modify(
        subscriptions.data[0].id,
        cancel_at_period_end=False
    )

