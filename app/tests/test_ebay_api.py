import logging
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from app.ebay.api import EbayAPI
from app.ebay.constants import MARKETPLACE_IDS
from app.models import Query, Item
from app import db
import requests_mock
import json

@pytest.fixture
def ebay_api():
    return EbayAPI(marketplace='EBAY_GB')

@pytest.fixture
def mock_response():
    def _mock_response(status=200, json_data=None, headers=None):
        response = Mock()
        response.status_code = status
        response.json.return_value = json_data or {}
        response.headers = headers or {}
        return response
    return _mock_response

def test_search_basic(ebay_api, mock_response):
    with patch('requests.get') as mock_get:
        mock_get.return_value = mock_response(json_data={
            'itemSummaries': [{'itemId': '123'}]
        })
        results = ebay_api.search("test")
        assert results['itemSummaries'][0]['itemId'] == '123'

def test_filter_building(ebay_api):
    filters = {
        'itemLocationCountry': 'US',
        'currency': 'USD',
        'min_price': 100,
        'max_price': 200,
    }
    mock_api = EbayAPI(marketplace='EBAY_US')
    filter_str = mock_api._build_filter(filters)
    assert filter_str == 'itemLocationCountry:US,currency:USD,price:[100..200]'

@patch('requests.get')
def test_pagination(mock_get, ebay_api, mock_response):
    mock_get.side_effect = [
        mock_response(json_data={
            'total': 250,
            'itemSummaries': [{'itemId': str(i)} for i in range(200)]
        }),
        mock_response(json_data={
            'itemSummaries': [{'itemId': str(i)} for i in range(200, 250)]
        })
    ]
    
    results = []
    offset = 0
    while True:
        batch = ebay_api.search("test", limit=200, offset=offset)
        results.extend(batch['itemSummaries'])
        if len(batch['itemSummaries']) < 200:
            break
        offset += 200
    
    assert len(results) == 250

@patch('requests.get')
def test_rate_limit_handling(mock_get, ebay_api, mock_response):
    mock_get.side_effect = [
        mock_response(status=429, headers={'Retry-After': '1'}),
        mock_response(json_data={'itemSummaries': []})
    ]
    
    results = ebay_api.search("test")
    assert mock_get.call_count == 2

def test_complex_filter(ebay_api):
    filters = {
        'itemLocationCountry': 'US',
        'currency': 'USD',
        'min_price': 50,
    }
    mock_api = EbayAPI(marketplace='EBAY_US')
    assert mock_api._build_filter(filters) == 'itemLocationCountry:US,currency:USD,price:[50..]'

def test_token_refresh_flow():
    api = EbayAPI()
    api.token_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
    
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            'access_token': 'new_token',
            'expires_in': 7200
        }
        token = api._get_token()
        
        assert token == 'new_token'
        assert api.token_expiry > datetime.now(timezone.utc)

def test_search_success(ebay_api):
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            'itemSummaries': [{'itemId': '123'}]
        }
        results = ebay_api.search("test")
        assert len(results['itemSummaries']) == 1

def test_filter_parsing(ebay_api):
    query = Mock()
    query.keywords = "test"
    query.filters = {
        'min_price': 100,
        'max_price': 200,
        'condition': ['new']
    }
    params = ebay_api.build_ebay_params(query)
    assert params['filter'] == 'price:[100..200],conditionIds:{1000}'

# New tests below
def test_min_price_only(ebay_api):
    query = Mock()
    query.keywords = "test"
    query.filters = {'min_price': 50}
    params = ebay_api.build_ebay_params(query)
    assert params['filter'] == 'price:[50..]'

def test_multiple_conditions(ebay_api):
    query = Mock()
    query.keywords = "test"
    query.filters = {'condition': ['used', 'refurbished']}
    params = ebay_api.build_ebay_params(query)
    assert 'conditionIds:{3000,2000}' in params['filter']

def test_no_filters(ebay_api):
    query = Mock()
    query.keywords = "test"
    query.filters = None
    params = ebay_api.build_ebay_params(query)
    assert 'filter' not in params

def test_max_price_only(ebay_api):
    query = Mock()
    query.keywords = "test"
    query.filters = {'max_price': 300}
    params = ebay_api.build_ebay_params(query)
    assert params['filter'] == 'price:[..300]'

def test_both_prices(ebay_api):
    query = Mock()
    query.keywords = "test"
    query.filters = {'min_price': 100, 'max_price': 200}
    params = ebay_api.build_ebay_params(query)
    assert params['filter'] == 'price:[100..200]'

@pytest.mark.skipif(
    not os.getenv('EBAY_CLIENT_ID') or 
    not os.getenv('EBAY_CLIENT_SECRET'),
    reason="Requires eBay CLIENT_ID and CLIENT_SECRET in .env"
)
def test_real_api_search(ebay_api):
    params = {'q': 'iphone', 'limit': 1}
    response = ebay_api.search(params)
    items = ebay_api.parse_response(response, query_id=1)
    
    print(f"First item keys: {items[0].keys()}")
    print(f"Sample item: {items[0]}")
    
    # Check dictionary structure
    assert len(items) > 0
    assert 'title' in items[0]
    assert 'price' in items[0]
    assert 'currency' in items[0]

@pytest.mark.skipif(
    not os.getenv('EBAY_CLIENT_ID') or 
    not os.getenv('EBAY_CLIENT_SECRET'),
    reason="Requires eBay CLIENT_ID and CLIENT_SECRET in .env"
)
def test_real_api_search_with_price_filter():
    ebay_api = EbayAPI(marketplace='EBAY_GB')
    # Test with price range filter
    filters = {
        'min_price': 200,
        'max_price': 400
    }
    print(("Searching in:"), ebay_api.marketplace)
    print(("Filters:"), filters)
    response = ebay_api.search('pokemon base set booster pack', filters=filters, limit=1)
    items = ebay_api.parse_response(response)
    
    print(f"First item keys: {items[0].keys()}")
    print(f"Sample item with price filter: {items[0]}")
    
    # Check dictionary structure and price filter
    assert len(items) > 0
    assert 'title' in items[0]
    assert 'original_price' in items[0]
    assert 'currency' in items[0]
    assert float(items[0]['original_price']) >= 200
    assert float(items[0]['original_price']) <= 400

def test_search_all_pages():
    ebay_api = EbayAPI(marketplace='EBAY_GB')
    items = ebay_api.search_all_pages("pokemon base set booster pack", filters={'itemLocationCountry': 'GB', 'priceCurrency': 'GBP', 'min_price': 30, 'max_price': 2000})
    print("Items length: ", len(items))
    print(f"First item keys: {items[0].keys()}")
    print(f"Sample item: {items[0]}")
    assert len(items) > 0
    assert isinstance(items[0], Item)

def test_ebay_search():
    api = EbayAPI()
    # Pass numeric values instead of strings
    results = api.search("test", {'min_price': 100.0})  
    assert len(results['itemSummaries']) > 0

@pytest.mark.parametrize("marketplace,currency,keywords", [
    ('EBAY_GB', 'GBP', "vintage camera"),
    ('EBAY_US', 'USD', "antique camera"),
    ('EBAY_DE', 'EUR', "alte kamera")
])
def test_marketplace_selection(ebay_api, marketplace, currency, keywords):
    """Test different marketplaces return correct currency"""
    api = EbayAPI(marketplace=marketplace)
    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json={
            'itemSummaries': [{
                'price': {'value': '100.00', 'currency': currency},
                'itemId': '123'
            }]
        })
        results = api.search(keywords)
        assert results['itemSummaries'][0]['price']['currency'] == currency


@pytest.mark.live
def test_live_marketplace_search():
    api = EbayAPI(marketplace='EBAY_US')
    results = api.search("iphone", limit=5)
    
    print(f"\nAPI Filters Used: {api._build_filter({})}")
    print(f"Response Items: {len(results['itemSummaries'])}")
    
    for item in results['itemSummaries']:
        print(f"\nItem: {item['title']}")
        print(f"Price: {item['price']['value']} {item['price']['currency']}")
        print(f"Location: {item.get('itemLocation',{}).get('country')}")
        print(f"URL: {item['itemWebUrl']}")
    
    # Verify all items are from US
    for item in results['itemSummaries']:
        assert item.get('itemLocation', {}).get('country') == 'US', f"Item location not US: {item.get('itemLocation')}"
    
    # Assertions remain the same