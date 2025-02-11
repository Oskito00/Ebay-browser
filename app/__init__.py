from flask import Flask
from app.extensions import db, migrate, login_manager, csrf, encryptor
from app.models import Query
from config import config  # Import the config dictionary
from flask_wtf.csrf import CSRFProtect
import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from .forms import csrf
from datetime import datetime
from apscheduler.jobstores.base import JobLookupError
import os

csrf = CSRFProtect()

scheduler = None

def create_app(config_class=config['default']):
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
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    encryptor.init_app(app)
    
    # Import models after extensions to avoid circular imports
    from app.models import User, Query
    
    # Register blueprints
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.queries import bp as queries_bp
    app.register_blueprint(queries_bp)

    from app.routes.telegram import bp as telegram_bp
    app.register_blueprint(telegram_bp, url_prefix='/telegram')
    
    with app.app_context():
        db.create_all()  # Ensure tables exist
    
    # Prevent scheduler from starting in reloader process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        if not hasattr(app, 'scheduler'):
            initialize_scheduler(app)
    
    return app

def initialize_scheduler(app):
    from app.jobs.query_jobs import check_query
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    
    app.logger.info("Initializing scheduler...")
    
    app.scheduler = BackgroundScheduler()
    
    with app.app_context():
        job_store = SQLAlchemyJobStore(engine=db.get_engine())
        app.scheduler.add_jobstore(job_store, 'default')
        app.scheduler.remove_all_jobs()
        
        queries = Query.query.all()
        app.logger.info(f"Scheduling {len(queries)} queries")
        
        for query in queries:
            job_id = f'query_{query.id}'
            app.scheduler.add_job(
                check_query,
                'interval',
                minutes=query.check_interval,
                args=[query.id],
                id=job_id,
                replace_existing=True
            )
        
        app.scheduler.start() 