import os
from dotenv import load_dotenv
import logging

load_dotenv()  # Load .env file

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-random-secret-key-here'
    SQLALCHEMY_DATABASE_URI = 'postgresql://ebay_user:secure_password@localhost/ebay_monitor'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EBAY_ENV = os.getenv('EBAY_ENV', 'sandbox')
    EBAY_API_URL = os.getenv('EBAY_API_URL')
    EBAY_CLIENT_ID = os.getenv('EBAY_CLIENT_ID')
    EBAY_CLIENT_SECRET = os.getenv('EBAY_CLIENT_SECRET')
    EBAY_ACCESS_TOKEN = os.getenv('EBAY_ACCESS_TOKEN')
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    WTF_CSRF_ENABLED = True  # Should be True in production
    WTF_CSRF_SECRET_KEY = os.getenv('CSRF_SECRET_KEY', 'fallback-secret-key')
    SQLALCHEMY_ECHO = False  # Disable raw SQL logging
    SQLALCHEMY_ENGINE_OPTIONS = {
        'echo_pool': False,
        'hide_parameters': True
    }
    LOG_LEVEL = logging.WARNING

    @classmethod
    def verify(cls):
        if not cls.ENCRYPTION_KEY:
            raise ValueError("ENCRYPTION_KEY must be set")

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://test_user@localhost/test_db' 