import pytest
from datetime import datetime, timedelta
from app.ebay.api import EbayAPI

@pytest.fixture
def api():
    return EbayAPI()

def test_auth_token_refresh(api):
    initial_token = api.token
    api.token_expiry = datetime.utcnow() - timedelta(seconds=1)
    
    # Trigger token refresh
    headers = api._get_auth_header()
    assert api.token != initial_token
    assert api.token_expiry > datetime.utcnow()

def test_search_basic(api):
    results = api.search_items("test search")
    assert isinstance(results, dict)
    assert 'itemSummaries' in results
    assert isinstance(results['itemSummaries'], list)

def test_search_with_filters(api):
    results = api.search_items(
        "laptop",
        filters={
            'min_price': 500,
            'max_price': 1000,
            'condition': ['3000']  # Used condition
        }
    )
    
    assert results.get('total') >= 0
    if results.get('itemSummaries'):
        item = results['itemSummaries'][0]
        assert 'itemId' in item
        assert 'title' in item
        assert 'price' in item

def test_filter_building(api):
    filters = {
        'min_price': 100,
        'max_price': 200,
        'condition': ['2000', '3000']
    }
    filter_str = api._build_filter(filters)
    assert filter_str == 'price:[100..200],conditionIds:{2000,3000}' 