import pytest
from app import create_app, db

@pytest.fixture(scope='module')
def test_client():
    app = create_app(config_class='config.TestConfig')
    testing_client = app.test_client()
    
    ctx = app.app_context()
    ctx.push()
    
    yield testing_client
    
    ctx.pop()

@pytest.fixture(scope='module')
def init_database():
    db.create_all()
    yield db
    db.session.remove()
    db.drop_all() 