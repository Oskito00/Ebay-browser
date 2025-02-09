import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.ebay.api import EbayAPI
from app.models import Query, Item
from app import db
from ..ebay.api import parse_ebay_response

@pytest.fixture
def ebay_api():
    return EbayAPI()

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
        'min_price': 100,
        'max_price': 200,
        'condition': ['3000']
    }
    filter_str = ebay_api._build_filter(filters)
    assert filter_str == 'price:[100..200],conditionIds:{3000}'

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
        'min_price': 50,
        'condition': ['2000', '2500']
    }
    assert ebay_api._build_filter(filters) == 'price:[50..],conditionIds:{2000,2500}'

@patch('requests.post')
def test_token_refresh(mock_post, ebay_api, mock_response):
    mock_post.return_value = mock_response(json_data={
        'access_token': 'new_token',
        'expires_in': 3600
    })
    
    ebay_api._refresh_token()
    assert ebay_api.token == 'new_token'
    assert isinstance(ebay_api.token_expiry, datetime)

def test_expired_token_refresh(ebay_api, mock_response):
    ebay_api.token_expiry = datetime.utcnow() - timedelta(minutes=1)
    with patch('requests.get') as mock_get:
        mock_get.return_value = mock_response(json_data={'itemSummaries': []})
        ebay_api.search("test")
        assert ebay_api.token is not None

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
    
    assert len(items) > 0
    assert isinstance(items[0], Item)


def test_parse_missing_image():
    sample = {
    'itemSummaries': [{
            'itemId': '123',
            'title': 'Test Item',
            'price': {'value': '100.00'},
            'itemWebUrl': 'http://test.com'
            # Missing 'image' field
        }]
    }
    items = parse_ebay_response(sample, 1)
    assert items[0].image_url is None