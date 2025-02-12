from dotenv import load_dotenv
from flask import Flask
from app.extensions import db, migrate, login_manager, csrf, encryptor
from app.models import Query
from config import config  # Import the config dictionary
from flask_wtf.csrf import CSRFProtect
import logging
from logging.handlers import RotatingFileHandler
from .forms import csrf
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine, inspect
import os
from app.cli import register_commands

csrf = CSRFProtect()

scheduler = None

def create_app(config_class='config.Config'):
    load_dotenv(override=True)
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set apscheduler logger level
    logging.getLogger('apscheduler').setLevel(logging.DEBUG)
    
    # Initialize CSRF after app creation
    csrf.init_app(app)  # Now 'app' exists
    
    # Initialize other extensions
    db.init_app(app)

    # Create jobstore within app context
    with app.app_context():
        app.scheduler_jobstore = SQLAlchemyJobStore(engine=db.get_engine())
    
    # Register CLI commands
    register_commands(app)

    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    encryptor.init_app(app)
        
    # Register blueprints
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.routes.queries import bp as queries_bp
    app.register_blueprint(queries_bp)

    from app.routes.telegram import bp as telegram_bp
    app.register_blueprint(telegram_bp, url_prefix='/telegram')
        
    return app