from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user, login_required
import stripe
from app.ebay.constants import TIER_LIMITS
from app.forms import SubscriptionActionForm
from app.models import db

bp = Blueprint('subscription', __name__)

@bp.route('/buy_subscription', methods=['GET', 'POST'])
def buy_subscription():
    form = SubscriptionActionForm()
    return render_template('subscription/buy_subscription.html', form=form)

@bp.route('/handle_actions', methods=['POST'])
@login_required
def handle_actions():
    print("User pressed button")
    form = SubscriptionActionForm()
    if not form.validate_on_submit():
        flash('Invalid form submission', 'danger')
        return redirect(url_for('subscription.buy_subscription'))
    
    action = form.action.data
    tier = form.tier.data
    when = form.when.data
    print(f"Action: {action}, Tier: {tier}, When: {when}")

    if action == 'cancel_subscription':
        downgrade_subscription('free')
    elif action == 'upgrade_subscription':
        upgrade_subscription(tier, when)
    elif action == 'downgrade_subscription':
        downgrade_subscription(tier)
    elif action == 'cancel_requested_change':
        cancel_requested_change()
    return redirect(url_for('subscription.buy_subscription'))

def upgrade_subscription(new_tier, when):
    print(f"Upgrading to {new_tier} at {when}")
    if when == 'now':
        current_user.subscription_valid_until = datetime.now(timezone.utc) + timedelta(days=30)
        current_user.auto_renew = True
        current_user.tier = {'tier': new_tier, 'query_limit': TIER_LIMITS[new_tier]}
        db.session.commit()
        flash(f'{new_tier.capitalize()} subscription activated!', 'success')
        return redirect(url_for('main.index'))
    elif when == 'next_renewal':
        print(f"User requested to change to {new_tier} at next renewal")
        current_user.requested_change = {'tier': new_tier, 'query_limit': TIER_LIMITS[new_tier]}
        db.session.commit()
        flash(f'Subscription upgrade requested!', 'success')
        return redirect(url_for('subscription.buy_subscription'))
    
def downgrade_subscription(new_tier):
    print(f"Downgrading to {new_tier}")
    print(f"Requested change: {current_user.requested_change}")
    if current_user.requested_change == {'tier': 'free', 'query_limit': 0}:
        current_user.auto_renew = False
    else:
        current_user.requested_change = {'tier': new_tier, 'query_limit': TIER_LIMITS[new_tier]}
    db.session.commit()
    flash(f'Subscription downgrade requested!', 'success')
    return redirect(url_for('subscription.buy_subscription'))

def cancel_requested_change():
    print("Cancelling requested change")
    current_user.requested_change = None
    db.session.commit()
    flash('Requested change cancelled!', 'success')
    return redirect(url_for('subscription.buy_subscription'))

#**********
# Stripe Integration
#**********


