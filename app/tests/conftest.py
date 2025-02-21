import pytest
from app import create_app, db
from app.models import User

# Fixture: Create a Flask app for testing
@pytest.fixture(scope='module')
def app():
    # 1. Create app with test config
    app = create_app(config_class='config.TestingConfig')
    
    # 2. Create fresh database tables
    with app.app_context():
        db.create_all()
        yield app  # Testing happens here
        db.drop_all()  # Cleanup after all tests

# Fixture: HTTP test client
@pytest.fixture
def client(app):
    return app.test_client()

# Fixture: Database session
@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()  # Undo uncommitted changes

# Fixture: Prepopulated test user
@pytest.fixture
def test_user(app):
    with app.app_context():
        user = User(email='test@example.com')
        db.session.add(user)
        db.session.commit()
        return user