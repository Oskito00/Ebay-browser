from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from app.extensions import db, csrf, encryptor
from app.forms import SettingsForm, DisconnectForm
from app.models import User
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from wtforms import ValidationError

bp = Blueprint('telegram', __name__, url_prefix='/telegram')

@bp.route('/connect', methods=['GET', 'POST'])
@login_required
def connect():
    form = SettingsForm()
    
    if form.validate_on_submit():
        chat_id = form.chat_id.data
        
        # Existing validation logic
        current_user.telegram_chat_id = chat_id
        db.session.commit()
        flash('Connected!', 'success')
        return redirect(url_for('main.settings'))
    
    return render_template(
        'telegram/connect.html',
        form=form
    )

@bp.route('/connect', methods=['POST'])
@login_required
def handle_connect():
    """Process Telegram chat ID submission"""
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        abort(400)
    
    chat_id = request.form.get('chat_id').strip()
    
    # Validation
    if not chat_id.isdigit():
        flash('Invalid Chat ID. Must contain only numbers.', 'danger')
        return redirect(url_for('telegram.connect'))
    
    # Check if already used
    existing_user = User.query.filter_by(telegram_chat_id=chat_id).first()
    if existing_user:
        flash('This Chat ID is already registered.', 'danger')
        return redirect(url_for('telegram.connect'))
    
    # Update user
    current_user.telegram_chat_id = chat_id
    current_user.telegram_connected = True
    db.session.commit()
    
    flash('Telegram account connected successfully!', 'success')
    return redirect(url_for('main.settings'))

@bp.route('/connection_status')
@login_required
def connection_status():
    user = User.query.get(current_user.id)
    return jsonify({
        'connected': bool(user.telegram_chat_id)
    })

@bp.route('/guide')
def setup_guide():
    return render_template('telegram/guide.html')

@bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@bp.route('/update-chat-id', methods=['POST'])
@login_required
def update_chat_id():
    new_chat_id = request.form.get('new_chat_id')
    
    if not new_chat_id.isdigit():
        flash('Invalid Chat ID format', 'danger')
        return redirect(url_for('main.settings'))
    
    current_user.telegram_chat_id = new_chat_id
    db.session.commit()
    flash('Chat ID updated successfully', 'success')
    return redirect(url_for('main.settings'))

@bp.route('/disconnect', methods=['POST'])
@login_required
def disconnect():
    current_user.telegram_chat_id = None
    db.session.commit()
    flash('Telegram disconnected', 'info')
    return redirect(url_for('main.settings'))