from datetime import datetime
import stripe

from app.ebay.constants import TIER_LIMITS
from app.models import User, db


def handle_invoice_paid(event):
    invoice = event['data']['object']
    
    # Get associated subscription
    subscription = stripe.Subscription.retrieve(invoice.subscription)
    
    # Get user from metadata
    user = User.query.get(subscription.metadata.user_id)
    
    if user:
        print(f"User found: {user.id}")
        print(f"Updating user's tier: {subscription.metadata.get('tier', 'free')}")
        # Update user's tier
        new_tier = subscription.metadata.get('tier', 'free')
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
        
        db.session.commit()

def handle_subscription_updated(event):
    sub = event['data']['object']
    user = User.query.filter_by(stripe_customer_id=sub.customer).first()
    
    if user:
        # Update period end
        user.current_period_end = datetime.fromtimestamp(sub.current_period_end)
        
        # Only update status if not pending cancellation
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