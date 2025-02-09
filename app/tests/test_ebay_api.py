import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.ebay.api import EbayAPI
from app.models import Query, Item
from app import db

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