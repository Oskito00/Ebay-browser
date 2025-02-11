import os
from dotenv import load_dotenv
import logging

load_dotenv()  # Load .env file

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-random-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EBAY_ENV = os.getenv('EBAY_ENV', 'sandbox')
    EBAY_API_URL = os.getenv('EBAY_API_URL')
    EBAY_CLIENT_ID = os.getenv('EBAY_CLIENT_ID', 'test-client-id')
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
    ENABLE_SCHEDULER = False  # Set to True when ready
    TESTING = False

    @classmethod
    def verify(cls):
        required = ['SECRET_KEY', 'EBAY_CLIENT_ID']
        for key in required:
            if not os.getenv(key) and not cls.__dict__.get(key):
                raise ValueError(f"Missing required config: {key}")

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://test_user@localhost/test_db'

class TestingConfig(Config):
    def __init__(self):
        super().__init__()
        self.TESTING = True
        self.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TELEGRAM_BOT_TOKEN = 'dummy-token' 