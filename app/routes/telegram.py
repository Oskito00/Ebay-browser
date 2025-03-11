from flask import Blueprint, current_app, render_template, request, jsonify, flash, redirect, url_for, abort
from app.extensions import db, csrf, encryptor
from app.forms import TelegramConnectForm, TelegramDisconnectForm
from app.models import User
from flask_login import current_user, login_required

from app.utils.notifications import NotificationManager

bp = Blueprint('telegram', __name__, url_prefix='/telegram')
@bp.route('/connect', methods=['GET', 'POST'])
@login_required
def connect():
    form = TelegramConnectForm(obj=current_user)

    if request.method == 'GET':
        # Correct way to populate FieldList
        if current_user.telegram_chat_ids:
            form.main_chat_id.data = current_user.telegram_chat_ids.get('main')
            # Clear existing entries first
            while len(form.additional_chat_ids) > 0:
                form.additional_chat_ids.pop_entry()
            # Add new entries
            for chat_id in current_user.telegram_chat_ids.get('additional', []):
                form.additional_chat_ids.append_entry(chat_id)
        return render_template('telegram/connect.html', form=form)
    
    if form.validate_on_submit():
        # Validate main ID uniqueness
        existing = User.query.filter(
        User.telegram_chat_ids['main'] == form.main_chat_id.data,
        User.id != current_user.id
        ).first()
        if existing and existing.id != current_user.id:
            flash('Main Chat ID already registered', 'danger')
            return redirect(url_for('telegram.connect'))
        
        # Process additional IDs
        additional_ids = [id.strip() for id in form.additional_chat_ids.data if id.strip()]
        

        print(f"User main chat id: {form.main_chat_id.data}")
        print(f"User additional chat ids: {additional_ids}")
        # Update user
        current_user.telegram_chat_ids = {
            'main': form.main_chat_id.data,
            'additional': additional_ids
        }
        current_user.telegram_connected = True
        db.session.commit()
        
        flash('Settings saved!', 'success')
        return redirect(url_for('settings.settings'))
    
    return render_template('telegram/connect.html', form=form)

@bp.route('/send_test_notification', methods=['GET'])
@login_required
def send_test_notification():
    print("Current user:", current_user)
    print("Current user telegram chat id:", current_user.telegram_chat_ids)
    print("Telegram bot token:", current_app.config['TELEGRAM_BOT_TOKEN'])
    NotificationManager.send_test_notification(current_user)
    return "Test notification sent"

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

@bp.route('/update-chat-id', methods=['POST'])
@login_required
def update_chat_id():
    chat_id = request.form.get('chat_id')
    
    if not chat_id.isdigit():
        flash('Invalid Chat ID format', 'danger')
        return redirect(url_for('main.settings'))
    
    current_user.telegram_chat_id = chat_id
    db.session.commit()
    flash('Chat ID updated successfully', 'success')
    return redirect(url_for('main.settings'))

@bp.route('/disconnect', methods=['POST'])
@login_required
def disconnect():
    current_user.telegram_chat_id = None
    current_user.telegram_connected = False
    db.session.commit()
    flash('Telegram disconnected', 'info')
    return redirect(url_for('main.settings'))