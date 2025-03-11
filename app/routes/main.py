from flask import Blueprint, render_template
from flask_login import current_user, login_required
from app.forms import TelegramConnectForm, TelegramDisconnectForm  # Import your forms

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html', user=current_user)


