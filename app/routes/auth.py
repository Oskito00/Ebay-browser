from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user
from app.models import User

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    if user and user.check_password(data['password']):
        login_user(user)
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid credentials'}), 401

@bp.route('/logout')
def logout():
    logout_user()
    return jsonify({'status': 'logged out'}) 