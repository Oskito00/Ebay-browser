from dotenv import load_dotenv
from flask import Flask
from app.extensions import db, migrate, login_manager, csrf, encryptor
from flask_wtf.csrf import CSRFProtect
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from .forms import csrf
import os
from app.scheduler import init_scheduler


csrf = CSRFProtect()

scheduler = None

def create_app(config_class=None):
    load_dotenv(override=True)
    app = Flask(__name__)

    #Initialises scheduler
    init_scheduler(app)

    # Determine configuration
    if config_class:
        app.config.from_object(config_class)
    else:
        env_config = os.getenv('FLASK_ENV', 'development').capitalize() + 'Config'
        app.config.from_object(f'config.{env_config}')
    
    # Configure logging only outside tests
    if not app.config.get('TESTING'):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.getLogger('apscheduler').setLevel(logging.INFO)
    
    # Initialize CSRF after app creation
    csrf.init_app(app)  # Now 'app' exists
    
    # Initialize other extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    encryptor.init_app(app)

    
    # Create jobstore within app context
    with app.app_context():
        app.scheduler_jobstore = SQLAlchemyJobStore(engine=db.get_engine())

    from app.scheduler.cli import start_scheduler
    app.cli.add_command(start_scheduler)

        
    # Register blueprints
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.routes.queries import bp as queries_bp
    app.register_blueprint(queries_bp)

    from app.routes.subscription import bp as subscription_bp
    app.register_blueprint(subscription_bp)

    from app.stripe.webhooks import webhook_bp
    app.register_blueprint(webhook_bp, url_prefix='/stripe')
    csrf.exempt(webhook_bp)

    from app.routes.telegram import bp as telegram_bp
    app.register_blueprint(telegram_bp, url_prefix='/telegram')

    from app.routes.settings import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')
        
    return app
