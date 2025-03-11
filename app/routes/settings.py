from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.forms import SettingsForm, TelegramConnectForm, TelegramDisconnectForm

bp = Blueprint('settings', __name__)

@bp.route('/')
@login_required
def settings():
    update_form = TelegramConnectForm()
    disconnect_form = TelegramDisconnectForm()
    return render_template(
        'settings.html',
        update_form=update_form,
        disconnect_form=disconnect_form
    )

@bp.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    form = SettingsForm(obj=current_user)
    # Handle form submission
    return redirect(url_for('settings.settings'))

@bp.route('/toggle_notification', methods=['POST'])
@login_required
def toggle_notification():
    """Update all notification preferences at once"""
    
    # Get current preferences or initialize if none exist
    prefs = current_user.notification_preferences or {}
    
    # Create a new dictionary to ensure SQLAlchemy detects the change
    new_prefs = {
        'price_drops': 'price_drops' in request.form,
        'new_items': 'new_items' in request.form,
        'auction_alerts': 'auction_alerts' in request.form
    }
    
    print("Form data:", request.form)
    print("Old prefs:", prefs)
    print("New prefs:", new_prefs)
    
    # Explicitly assign the new dictionary to trigger SQLAlchemy change detection
    current_user.notification_preferences = new_prefs
    
    # Mark the user as modified to force an update
    db.session.add(current_user)
    db.session.commit()
    
    # Verify the changes after commit
    db.session.refresh(current_user)
    print("After commit:", current_user.notification_preferences)
    
    flash('Notification preferences updated successfully', 'success')
    return redirect(url_for('settings.settings'))

