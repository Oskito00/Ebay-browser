from datetime import datetime
from flask import Blueprint, current_app, jsonify, render_template, request, flash, redirect, session, url_for, abort
from flask_login import current_user, login_required
import stripe
from app.forms import SubscriptionActionForm
from flask_wtf.csrf import CSRFProtect
from app.extensions import db
from app.stripe.stripe_fulfillment import get_tier_from_price

csrf = CSRFProtect()
bp = Blueprint('subscription', __name__, url_prefix='/subscription')


@bp.route('/buy_subscription', methods=['GET', 'POST'])
def buy_subscription():
    form = SubscriptionActionForm()
    return render_template('subscription/buy_subscription.html', form=form)

#**********
# Stripe Integration
#**********

@bp.route('/handle_actions', methods=['POST'])
@login_required
def handle_actions():
    """
    Handles the actions for subscription changes
    """
    action = request.form.get('action')
    if action == 'create_checkout_session':
        return create_checkout_session()
    if action == 'schedule_cancellation':
        return schedule_cancellation()
    if action == 'upgrade_subscription':
        return upgrade_subscription()
    if action == 'resume_subscription':
        return resume_subscription()
    if action == 'schedule_downgrade':
        return schedule_downgrade()

def create_checkout_session():
    # Get the price id and tier from the form
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    print("Creating checkout session")
    price_id = request.form.get('price_id')
    print(f"Price ID: {price_id}")
    tier = request.form.get('tier')
    print(f"Tier: {tier}")
    print("trying to create checkout session")

    # Ensuring the customer exists in Stripe and creating them if not...
    if not current_user.stripe_customer_id:
        print("No customer found, creating one")
        customer = stripe.Customer.create(
                email=current_user.email,
                metadata={'user_id': current_user.id}
            )
        current_user.stripe_customer_id = customer.id
        db.session.commit()
    else:
        print("Customer found: ", current_user.stripe_customer_id)

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=url_for(
                'subscription.payment_success', _external=True
            ),
            cancel_url=url_for(
                'subscription.payment_cancel', _external=True
            )
        )
        print(f"Checkout session created: {checkout_session}")
        current_user.last_checkout_session_id = checkout_session.id
        db.session.commit()

    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return str(e)

    return redirect(checkout_session.url, code=303)

def schedule_cancellation():
    """Schedules a subscription cancellation for the current user"""
    print("Scheduling cancellation")
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    try:
        # Get active subscription
        subs = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status='active'
        ).data
        
        if not subs:
            flash('No active subscription', 'warning')
            return redirect(url_for('subscription.buy_subscription'))
        
        # Schedule cancellation
        stripe.Subscription.modify(
            subs[0].id,
            cancel_at_period_end=True
        )
        
        print("Changing the cancellation request to true")
        # Record cancellation request in the database
        current_user.cancellation_requested = True
        current_user.subscription_status = 'pending_cancellation'
        print("Committing the changes to the database")
        db.session.commit()
        
        flash('Cancellation scheduled for period end', 'info')
        return redirect(url_for('subscription.buy_subscription'))
    
    except stripe.error.StripeError as e:
        flash(f'Error: {e.user_message}', 'danger')
        print(f"Error: {e.user_message}")
        return redirect(url_for('subscription.buy_subscription'))
    
def resume_subscription():
    """Resumes a subscription for the current user"""
    print("Resuming subscription")
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    try:
        # Get active subscription
        subs = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status='active'
        ).data
        
        if not subs:
            flash('No active subscription', 'warning')
            return redirect(url_for('subscription.buy_subscription'))
        
        # Resume subscription
        stripe.Subscription.modify(
            subs[0].id,
            cancel_at_period_end=False
        )
        
        print("Changing the cancellation request to false")
        # Record cancellation request in the database
        current_user.cancellation_requested = False
        current_user.subscription_status = 'active'
        print("Committing the changes to the database")
        db.session.commit()
        
        flash('Subscription resumed', 'info')
        return redirect(url_for('subscription.buy_subscription'))
    
    except stripe.error.StripeError as e:
        flash(f'Error: {e.user_message}', 'danger')
        print(f"Error: {e.user_message}")
        return redirect(url_for('subscription.buy_subscription'))
    

def upgrade_subscription():
    print("Upgrading subscription")
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    new_price_id = request.form.get('price_id')
    
    try:
        subs = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status='active'
        ).data
        
        if not subs:
            flash('No active subscription', 'warning')
            return redirect(url_for('subscription.buy_subscription'))
        

        # Get subscription item ID
        items = stripe.SubscriptionItem.list(
            subscription=subs[0].id,
            limit=1
        )
        item_id = items.data[0].id

        # Immediate upgrade with proration
        updated_sub = stripe.Subscription.modify(
            subs[0].id,
            items=[{
                'id': item_id,
                'price': new_price_id
            }],
            proration_behavior='always_invoice'
        )
        
        #Optimistically update the tier
        #Will revert if payment fails
        current_user.tier = get_tier_from_price(new_price_id)
        db.session.commit()
        
        flash('Subscription upgraded successfully', 'success')
        return redirect(url_for('subscription.buy_subscription'))
    
    except stripe.error.StripeError as e:
        flash(f'Error: {e.user_message}', 'danger')
        return redirect(url_for('subscription.buy_subscription'))

def schedule_downgrade():
    new_price_id = request.form.get('price_id')
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    try:
        # Get active subscription
        subs = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status='active'
        ).data
        
        if not subs:
            flash('No active subscription', 'warning')
            return redirect(url_for('subscription.buy_subscription'))
        
        # Get subscription item ID
        items = stripe.SubscriptionItem.list(
            subscription=subs[0].id,
            limit=1
        )
        item_id = items.data[0].id
        
        # Schedule downgrade for next period
        stripe.Subscription.modify(
            subs[0].id,
            items=[{
                'id': item_id,
                'price': new_price_id
            }],
            billing_cycle_anchor='unchanged',
            proration_behavior='none'
        )
        
        # Store pending downgrade
        current_user.pending_tier = get_tier_from_price(new_price_id)
        current_user.pending_effective_date = datetime.fromtimestamp(
            subs[0].current_period_end
        )
        db.session.commit()
        
        flash('Downgrade scheduled for next billing cycle', 'info')
        return redirect(url_for('subscription.buy_subscription'))
    
    except stripe.error.StripeError as e:
        flash(f'Error: {e.user_message}', 'danger')
        return redirect(url_for('subscription.buy_subscription'))


@bp.route('/payment_success', methods=['GET'])
def payment_success():
    return render_template('subscription/payment_success.html')

@bp.route('/payment_cancel', methods=['GET'])
def payment_cancel():
    return render_template('subscription/payment_cancel.html')
