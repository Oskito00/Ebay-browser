import os
from dotenv import load_dotenv
import logging
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine

load_dotenv()  # Load .env file

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'another-fallback-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL','sqlite:///app.db')
    TIMEZONE = os.getenv('TIMEZONE', 'Europe/London')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EBAY_ENV = os.getenv('EBAY_ENV', 'sandbox')
    EBAY_API_URL = os.getenv('EBAY_API_URL')
    EBAY_CLIENT_ID = os.getenv('EBAY_CLIENT_ID')
    EBAY_CLIENT_SECRET = os.getenv('EBAY_CLIENT_SECRET')
    EBAY_ACCESS_TOKEN = os.getenv('EBAY_ACCESS_TOKEN')
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.getenv('CSRF_SECRET', 'fallback-secret-key')
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    SQLALCHEMY_ECHO = False  # Disable raw SQL logging
    SQLALCHEMY_ENGINE_OPTIONS = {
        'echo_pool': False,
        'hide_parameters': True
    }
    LOG_LEVEL = 'INFO'
    TESTING = False

    @classmethod
    def verify(cls):
        """Validate required settings"""
        if not cls.EBAY_CLIENT_ID or not cls.EBAY_CLIENT_SECRET:
            raise ValueError("Missing eBay API credentials")

    @classmethod
    def get(cls, key, default=None):
        return getattr(cls, key, default)

class TestingConfig(Config):
    EBAY_CLIENT_ID = os.getenv('EBAY_CLIENT_ID')
    EBAY_CLIENT_SECRET = os.getenv('EBAY_CLIENT_SECRET')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    TESTING = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_BOT_TOKEN = '7914809074'

class SchedulerConfig:
    # Use main app's database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///instance/app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    SCHEDULER_JOBSTORES = {
        'default': SQLAlchemyJobStore(
            engine=create_engine(SQLALCHEMY_DATABASE_URI)
        )
    }
    
    SCHEDULER_TIMEZONE = 'UTC'

class DevelopmentConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False

config = {
    'development': Config,
    'default': Config,
    'testing': TestingConfig
} 