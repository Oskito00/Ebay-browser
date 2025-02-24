import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Query, Item
from app.jobs.query_check import process_items, full_scrape_job, recent_scrape_job
from unittest.mock import patch

@pytest.fixture
def app():
    app = create_app(config_class='config.TestingConfig')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def test_user(app):
    user = User(
        email='test@example.com',
        telegram_chat_id='123',
        notification_preferences={
            'price_drops': True,
            'auction_alerts': True
        }
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def test_query(test_user):
    query = Query(
        keywords="test query",
        min_price=10.0,
        max_price=100.0,
        check_interval=30,
        user=test_user
    )
    db.session.add(query)
    db.session.commit()
    return query

#****************************
# Test processing items logic
#****************************
def test_process_items_new_item(app, test_query):
    test_data = [{
        'ebay_id': '123',
        'title': 'Test Item',
        'price': 50.0,
        'currency': 'GBP',
        'query_id': test_query.id,
        'url': 'http://test.com',
        'last_updated': datetime.utcnow()
    }]
    
    with app.app_context():
        new, updated = process_items(test_data, test_query)
        assert len(new) == 1
        assert len(updated) == 0
        item = Item.query.first()
        assert item.title == 'Test Item'

def test_process_items_update_price(app, test_query):
    # Set query max price
    test_query.max_price = 70.0
    db.session.commit()
    
    # Existing item above max price
    existing = Item(
        ebay_id='123',
        price=80.0,  # Above max
        query_id=test_query.id,
        title='Existing Item',
        currency='GBP',
        url='http://example.com/existing'
    )
    db.session.add(existing)
    db.session.commit()
    
    test_data = [{
        'ebay_id': '123', 
        'price': 65.0,  # Below max
        'query_id': test_query.id,
        'title': 'Updated Item',
        'currency': 'GBP',
        'url': 'http://example.com/updated'
    }]
    
    with app.app_context(), \
         patch('app.utils.notifications.NotificationManager.send_price_drops') as mock_send:
        new, updated = process_items(test_data, test_query, 
                                    check_existing=True, full_scan=True)
        
        mock_send.assert_called_once()
        assert existing.price == 65.0

@patch('app.jobs.job_management.scrape_ebay')
def test_full_scrape_job(mock_scrape, app, test_query):
    # Mock return value with complete item data
    mock_scrape.return_value = [{
        'ebay_id': '456', 
        'title': 'Full Test',
        'price': 75.0,
        'currency': 'GBP',
        'query_id': test_query.id,
        'url': 'http://example.com/full',
        'keywords': test_query.keywords,
        'last_updated': datetime.utcnow()
    }]
    
    with app.app_context():
        with db.session() as session:  # Use context manager
            full_scrape_job(test_query.id)
            updated_query = session.get(Query, test_query.id)
            
            # Verify item creation
            item = Item.query.filter_by(ebay_id='456').first()
            assert item is not None, "Item was not created"
            assert item.title == 'Full Test'
            
            # Verify query timestamps
            assert updated_query.last_full_run is not None
            assert updated_query.next_full_run > datetime.utcnow()

@patch('app.jobs.job_management.scrape_new_items')
def test_recent_scrape_job(mock_scrape, app, test_query):
    mock_scrape.return_value = [{
        'ebay_id': '789', 
        'title': 'Recent Test',
        'price': 45.0,
        'query_id': test_query.id
    }]
    
    with app.app_context():
        recent_scrape_job(test_query.id)
        item = Item.query.filter_by(ebay_id='789').first()
        assert item is not None

def test_notification_preferences(app, test_user):
    # Create associated query
    query = Query(
        keywords="test",
        user=test_user,
        min_price=10.0,
        max_price=100.0,
        check_interval=30
    )
    db.session.add(query)
    db.session.commit()
    
    test_data = [{
        'ebay_id': '123', 
        'price': 50.0,
        'query_id': query.id,
        'title': 'Test Item',
        'currency': 'GBP',
        'url': 'http://example.com/item123'
    }]
    
    with app.app_context(), \
         patch('app.utils.notifications.NotificationManager.send_price_drops') as mock_send:
        process_items(test_data, query)
        mock_send.assert_not_called()


