from flask import Flask
from app.extensions import db, migrate, login_manager, csrf, encryptor
from config import Config
from flask_wtf.csrf import CSRFProtect
import logging
from logging.handlers import RotatingFileHandler

csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Verify configuration
    config_class.verify()
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    encryptor.init_app(app)
    
    # Import models after extensions to avoid circular imports
    from app.models import User
    
    # Register blueprints
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.queries import bp as queries_bp
    app.register_blueprint(queries_bp)
    
    with app.app_context():
        db.create_all()  # Ensure tables exist
    
    print("Current DB URI:", app.config['SQLALCHEMY_DATABASE_URI'])
    
    # Configure logging
    if not app.debug:
        file_handler = RotatingFileHandler(
            'app.log',
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(app.config['LOG_LEVEL'])
        app.logger.addHandler(file_handler)
        app.logger.setLevel(app.config['LOG_LEVEL'])
        
        # Silence SQLAlchemy and Werkzeug
        logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    return app 