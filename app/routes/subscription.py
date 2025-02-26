from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from app.forms import SubscriptionForm
from app.models import db

bp = Blueprint('subscription', __name__)

@bp.route('/buy_subscription', methods=['GET', 'POST'])
def buy_subscription():
    form = SubscriptionForm()
    if form.validate_on_submit():
        return create_subscription()
    return render_template('subscription/buy_subscription.html', form=form)

@bp.route('/create_subscription', methods=['POST'])
@login_required
def create_subscription():
    form = SubscriptionForm()
    if not form.validate_on_submit():
        flash('Invalid form submission', 'danger')
        return redirect(url_for('subscription.buy_subscription'))
    
    tier = form.tier.data
    print("Selected tier:", tier)
    if tier == 'individual':
        current_user.query_limit = 1500
    elif tier == 'business':
        current_user.query_limit = 4000
    else:
        flash('Invalid subscription tier', 'danger')
        return redirect(url_for('subscription.buy_subscription'))
    
    db.session.commit()
    flash(f'{tier.capitalize()} subscription activated!', 'success')
    return redirect(url_for('main.dashboard'))