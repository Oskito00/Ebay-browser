import os
from dotenv import load_dotenv
import logging
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine

load_dotenv(override=True)  # Load .env file

project_root = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'another-fallback-key')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(project_root, "instance/app.db")}'
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

    #Stripe
    STRIPE_PRICE_INDIVIDUAL = os.getenv('STRIPE_PRICE_INDIVIDUAL')
    STRIPE_PRICE_BUSINESS = os.getenv('STRIPE_PRICE_BUSINESS')
    STRIPE_PRICE_PRO = os.getenv('STRIPE_PRICE_PRO')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

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

class SchedulerConfig(Config):
    # Inherit DB settings
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(project_root, "instance/app.db")}'

    # Disable unnecessary features
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class DevelopmentConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False

config = {
    'development':  DevelopmentConfig,
    'default': Config,
    'testing': TestingConfig
} 