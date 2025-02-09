import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-123')
    SQLALCHEMY_DATABASE_URI = 'postgresql://ebay_user:secure_password@localhost/ebay_monitor'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EBAY_CLIENT_ID = os.getenv('EBAY_CLIENT_ID')
    EBAY_CLIENT_SECRET = os.getenv('EBAY_CLIENT_SECRET')
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

    @classmethod
    def verify(cls):
        if not cls.ENCRYPTION_KEY:
            raise ValueError("ENCRYPTION_KEY must be set")

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://test_user@localhost/test_db' 