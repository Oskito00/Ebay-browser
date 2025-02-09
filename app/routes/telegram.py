from flask import Blueprint, render_template, request, jsonify
from app.extensions import db, csrf, encryptor
from app.models import User
from flask_login import current_user, login_required

bp = Blueprint('telegram', __name__, url_prefix='/telegram')

@bp.route('/connect', methods=['GET', 'POST'])
@csrf.exempt  # If using API-style form
@login_required
def connect_telegram():
    if request.method == 'GET':
        return render_template('telegram/connect.html')
    
    # POST handling
    user = current_user  # Replace get_current_user()
    data = request.get_json()
    
    if not data or 'chat_id' not in data:
        return jsonify({'error': 'Missing chat ID'}), 400
    
    try:
        user.telegram_chat_id = data['chat_id']
        user.telegram_notifications_enabled = True
        db.session.commit()
        encrypted_id = encryptor.encrypt(data['chat_id'])
        return jsonify({
            'status': 'success',
            'message': 'Telegram notifications enabled',
            'encrypted_id': encrypted_id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/guide')
def setup_guide():
    return render_template('telegram/guide.html') 