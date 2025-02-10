from flask import Blueprint, render_template
from flask_login import current_user, login_required
from app.forms import SettingsForm, DisconnectForm  # Import your forms

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html', user=current_user)

@bp.route('/settings')
@login_required
def settings():
    update_form = SettingsForm()
    disconnect_form = DisconnectForm()
    return render_template(
        'telegram/settings.html',
        update_form=update_form,
        disconnect_form=disconnect_form
    )
