from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from app.utils.security import DataEncryptor

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
encryptor = DataEncryptor()

# User loader must be after model definition
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))

login_manager.user_loader(load_user) 