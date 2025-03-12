from flask import Blueprint, render_template, request, session
from flask_login import current_user, login_required
from app.forms import TelegramConnectForm, TelegramDisconnectForm  # Import your forms

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html', user=current_user)

@bp.before_app_request
def track_queries():
    if 'query_count' not in session:
        session['query_count'] = 0
    if request.method == 'POST':  # Or only count specific actions
        session['query_count'] += 1
        session.modified = True


