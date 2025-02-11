import pytest
import os
from pathlib import Path
from dotenv import load_dotenv
from app import create_app, db as _db
from config import TestingConfig
from sqlalchemy.orm import sessionmaker, scoped_session

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

@pytest.fixture(scope='session')
def app():
    app = create_app(TestingConfig)
    app_context = app.app_context()
    app_context.push()
    yield app
    app_context.pop()

@pytest.fixture(scope='session')
def db(app):
    _db.create_all()
    yield _db
    _db.drop_all()

@pytest.fixture(scope='function')
def session(db):
    connection = db.engine.connect()
    transaction = connection.begin()
    
    # Create session using the connection
    session_factory = sessionmaker(bind=connection)
    session = scoped_session(session_factory)
    
    # Patch the database session
    db.session = session
    
    yield session
    
    transaction.rollback()
    connection.close()
    session.remove()