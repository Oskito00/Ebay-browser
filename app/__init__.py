from flask import Flask
from app.extensions import db, migrate, login_manager, csrf, encryptor
from config import Config
from flask_wtf.csrf import CSRFProtect
import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

csrf = CSRFProtect()

scheduler = None

def create_app(config_class='config.Config'):
    global scheduler
    app = Flask(__name__)
    app.config.from_object(config_class)
    csrf.init_app(app)

    # Verify configuration
    config_class.verify()
    
    # Initialize extensions
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
    
    # Conditionally start scheduler
    if app.config['ENABLE_SCHEDULER']:
        from app.jobs.query_jobs import check_query
        
        scheduler = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(engine=db.engine)})
        
        for query in Query.query.all():
            scheduler.add_job(
                check_query,
                'interval',
                minutes=query.check_interval,
                args=[query.id],
                id=f'query_{query.id}'
            )
        
        scheduler.start()
    
    return app 