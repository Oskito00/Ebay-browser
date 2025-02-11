from unittest.mock import patch  # Correct import
from app.ebay.api import EbayAPI
from app.jobs.query_jobs import check_query
from app.models import Item, Query, User
import pytest
from flask import current_app

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    # Set required environment variables
    monkeypatch.setenv('EBAY_CLIENT_ID', 'test-client-id')
    monkeypatch.setenv('EBAY_CLIENT_SECRET', 'test-secret')
    monkeypatch.setenv('ENCRYPTION_KEY', 'test-encryption-key')

@pytest.fixture(autouse=True)
def setup_config(monkeypatch):
    # Set config values directly
    current_app.config.update(
        EBAY_CLIENT_ID='test-client-id',
        EBAY_CLIENT_SECRET='test-secret'
    )

@pytest.fixture(autouse=True)
def mock_entire_api():
    with patch('app.ebay.api.requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            'access_token': 'fake-token',
            'expires_in': 3600
        }
        yield

@pytest.fixture(autouse=True)
def mock_ebay_client():
    with patch('app.utils.scraper.create_ebay_client') as mock_client:
        mock_api = mock_client.return_value
        mock_api.search_all_pages.return_value = [{
            'ebay_id': '123',
            'title': 'Test Item',
            'price': 29.99,
            'currency': 'USD',
            'url': 'http://test.item'
        }]
        yield

def test_check_query_initial_run(session):  # Use session fixture
    # Setup
    user = User(email='test@example.com', password_hash='dummy')
    session.add(user)
    session.commit()
    
    query = Query(
        keywords="test search",
        check_interval=5,
        user_id=user.id
    )
    session.add(query)
    session.commit()

    print(f"Query {query.id}: {query}")
    print("Query is: ", query.keywords)
    print("Filters are: ", query.filters)
    
    with patch('app.utils.scraper.create_ebay_client') as mock_client:
        # Mock API client creation
        mock_api = mock_client.return_value
        mock_api.search_all_pages.return_value = [{
            'ebay_id': '123',
            'title': 'Test Item',
            'price': 29.99,
            'currency': 'USD',
            'url': 'http://test.item'
        }]
        
        check_query(query.id)
        session.commit()
    
    assert session.query(Item).count() == 1

def test_ebay_api_requires_credentials(monkeypatch):
    # Clear environment and config
    monkeypatch.delenv('EBAY_CLIENT_ID', raising=False)
    monkeypatch.delenv('EBAY_CLIENT_SECRET', raising=False)
    
    from flask import current_app
    current_app.config['EBAY_CLIENT_ID'] = None
    current_app.config['EBAY_CLIENT_SECRET'] = None
    
    with pytest.raises(ValueError):
        from app.ebay.api import EbayAPI
        EbayAPI()

def test_check_query_paginated_results(session):
    # Setup
    user = User(email='test@example.com', password_hash='dummy')
    session.add(user)
    session.commit()
    
    query = Query(
        keywords="test pagination",
        check_interval=5,
        user_id=user.id
    )
    session.add(query)
    session.commit()

    # Mock scrape_ebay instead of EbayAPI
    with patch('app.jobs.query_jobs.scrape_ebay') as mock_scrape:
        mock_scrape.return_value = [
            {
                'ebay_id': '1',
                'title': 'Item 1',
                'price': 10.0,
                'currency': 'USD',
                'url': 'http://item1'
            },
            {
                'ebay_id': '2',
                'title': 'Item 2',
                'price': 20.0,
                'currency': 'USD',
                'url': 'http://item2'
            },
            {
                'ebay_id': '3',
                'title': 'Item 3',
                'price': 30.0,
                'currency': 'USD',
                'url': 'http://item3'
            }
        ]
        
        check_query(query.id)
        session.commit()
    
    # Verify
    assert session.query(Item).count() == 3
    items = session.query(Item).order_by(Item.price).all()
    assert [item.price for item in items] == [10.0, 20.0, 30.0]


def test_search_with_marketplace(mock_entire_api):
    with patch('app.ebay.api.EbayAPI.search') as mock_search:
        mock_search.return_value = {'total': 1, 'items': [{'id': '123'}]}
        
        api = EbayAPI()
        api.search_all_pages(
            "test",
            marketplace='EBAY_DE'
        )
        
        assert api.marketplace == 'EBAY_DE'

def test_scraper_called_correctly(session):
    # Create user first
    user = User(email='test@example.com', password_hash='dummy')
    session.add(user)
    session.commit()
    
    # Create query with user association
    query = Query(
        keywords="test",
        check_interval=5,
        user_id=user.id  # Link to user
    )
    session.add(query)
    session.commit()
    
    with patch('app.jobs.query_jobs.scrape_ebay') as mock_scrape:
        mock_scrape.return_value = []
        check_query(query.id)
        mock_scrape.assert_called_once_with(
            keywords=query.keywords,
            filters={
                'min_price': query.min_price,
                'max_price': query.max_price,
                'item_location': query.item_location
            },
            marketplace=query.marketplace
        )

