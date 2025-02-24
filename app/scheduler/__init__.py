from flask import Flask
from app.extensions import db
from config import SchedulerConfig

def create_scheduler_app():
    """Create a minimal Flask app for scheduler context"""
    app = Flask(__name__)
    app.config.from_object(SchedulerConfig)
    
    # Initialize only the database
    db.init_app(app)
    
    return app