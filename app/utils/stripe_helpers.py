from datetime import datetime
import stripe

from app.ebay.constants import TIER_LIMITS
from app.models import User, db


def handle_invoice_paid(event):
    invoice = event['data']['object']

    if invoice.billing_reason in ['subscription_update', 'subscription_cycle']:
        return
    
    # Get associated subscription
    subscription = stripe.Subscription.retrieve(invoice.subscription)
    # Get user from metadata
    user = User.query.get(subscription.metadata.user_id)
    if user:
        print(f"User found: {user.id}")
        print(f"Updating user's tier: {subscription.metadata.get('tier', 'free')}")
        # Update user's tier
        new_tier = subscription.metadata.get('tier', 'free')
        print(f"New tier: {new_tier}")
        if invoice.billing_reason == "subscription_create":
            #Set their tier to the new tier
            user.tier = {'name': new_tier, 'query_limit': TIER_LIMITS[new_tier]}
            user.requested_change = None
            user.subscription_status = 'active'
            user.current_period_end = datetime.fromtimestamp(subscription.current_period_end)
            db.session.commit()
            print(f"User's tier updated to: {user.tier}")
        if invoice.billing_reason == 'subscription_update':
            print(f"User requested change: {user.requested_change}")
            user.tier = {user.requested_change['name']: user.requested_change['query_limit']}
            user.requested_change = None
            user.current_period_end = datetime.fromtimestamp(subscription.current_period_end)
            db.session.commit()
        else:
            user.tier = {
                'name': new_tier,
                'query_limit': TIER_LIMITS[new_tier]
            }
        
        # Update subscription period
        user.current_period_end = datetime.fromtimestamp(
            subscription.current_period_end
        )
        
        # Update status
        user.subscription_status = 'active'
        user.auto_renew = True
    else:
        print(f"User not found")
        
        db.session.commit()

def handle_subscription_updated(event):
    """Handle subscription updated event"""
    sub = event['data']['object']
    print(f"Subscription customer: {sub.customer}")
    user = User.query.filter_by(stripe_customer_id=sub.customer).first()
    print(user)
    
    #If the user requests to update immediately, we need to update the tier and requested_change
    if user.requested_change and user.requested_change.get('when') == 'now':
        print(f"User requested change: {user.requested_change}")
        user.tier ={user.requested_change['name']: user.requested_change['query_limit']}
        user.requested_change = None
        print("Updated user tier to: ", user.tier)
        db.session.commit()
        #update the subscription end date
        print("Updating user period end to: ", sub.current_period_end)
        user.current_period_end = datetime.fromtimestamp(sub.current_period_end)

        # If the user has requested to cancel, we need to update the subscription status
        print(f"User cancellation requested: {user.cancellation_requested}")
        if user.cancellation_requested == True:
            user.subscription_status = 'pending_cancellation'
        elif user.cancellation_requested == False:
            user.subscription_status = 'active'
        else:
            user.subscription_status = sub.status
        
        db.session.commit()

def handle_subscription_deleted(event):
    print("Subscription deleted event received")
    sub = event['data']['object']
    print(sub)
    # Only handle canceled-at-period-end subscriptions
    if not sub.cancel_at_period_end:
        return

    user = User.query.filter_by(stripe_customer_id=sub.customer).first()
    print("User found: ", user.id)
    print("Subscription status: ", user.subscription_status)
    if user:
        
        # Verify expiration date
        print("Setting user to expired")
        user.tier = {'name': 'free', 'query_limit': 0}
        user.subscription_status = 'expired'
        user.current_period_end = None
        user.requested_change = None
        user.cancellation_requested = False
        db.session.commit()
        print(f"Downgraded user {user.id} to free tier")
