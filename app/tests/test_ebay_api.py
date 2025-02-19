import logging
import os
from re import match
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from app.ebay.api import EbayAPI
from app.ebay.constants import MARKETPLACE_IDS
from app.models import Query, Item
from app import db
import requests_mock
import json
from app import create_app
from requests.exceptions import HTTPError

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

@pytest.fixture
def mock_items():
    return [
        {'title': 'Charizard Card Holo', 'price': 100},
        {'title': 'Shadowless Charizard Card', 'price': 200},
        {'title': 'Pikachu Rare Card', 'price': 50}
    ]

@pytest.fixture
def mock_ebay_api(mocker, mock_items):
    api = EbayAPI()
    mocker.patch.object(api, 'search', return_value={'items': mock_items})
    return api

#***********************
#Keyword Filtering Tests
#***********************

def test_required_keywords(app, mock_ebay_api, mock_items):
    with app.app_context():
        filtered = mock_ebay_api._filter_items(
            mock_items, 
            required_keywords='charizard',
            excluded_keywords=''
        )
        assert len(filtered) == 2

def test_excluded_keywords(app, mock_ebay_api, mock_items):
    # Test single exclusion
    with app.app_context():
        filtered = mock_ebay_api._filter_items(
        mock_items,
        required_keywords='',
        excluded_keywords='base'
    )
        assert len(filtered) == 3
        assert all('base' not in item['title'].lower() for item in filtered)
    
        # Test multiple exclusions
        filtered = mock_ebay_api._filter_items(
        mock_items,
        required_keywords='',
        excluded_keywords='base,shadowless'
        )
        assert len(filtered) == 2

def test_combined_filters(app,mock_ebay_api, mock_items):
    with app.app_context():
        filtered = mock_ebay_api._filter_items(
            mock_items,
            required_keywords='card',
            excluded_keywords='rare'
        )
        # Should get first 2 items
        assert len(filtered) == 2
        assert all('card' in item['title'].lower() for item in filtered)
        assert all('rare' not in item['title'].lower() for item in filtered)

def test_empty_filters(app, mock_ebay_api, mock_items):
    with app.app_context():
        filtered = mock_ebay_api._filter_items(
            mock_items,
            required_keywords='',
            excluded_keywords=''
        )
    assert len(filtered) == len(mock_items)

def test_no_matches(app, mock_ebay_api, mock_items):
    with app.app_context():
        filtered = mock_ebay_api._filter_items(
            mock_items,
            required_keywords='mewtwo',
            excluded_keywords=''
        )
    assert len(filtered) == 0

#***********************
#Condition Filtering Tests
#***********************

def test_condition_filter_combinations(app):
    with app.app_context():
        api = EbayAPI()
        
        # Test Any Condition (empty string)
        filters = {'condition': ''}
        assert 'conditions' not in api._build_filter(filters)
    
        # Test New Condition
        filters = {'condition': 'NEW'}
        assert 'conditions:{NEW}' in api._build_filter(filters)
    
        # Test Used Condition 
        filters = {'condition': 'USED'}
        assert 'conditions:{USED}' in api._build_filter(filters)
    
        # Test invalid condition
        filters = {'condition': 'RENEWED'}
        assert 'conditions' not in api._build_filter(filters)

#***********************
#Buying Options Filtering Tests
#***********************

def test_buying_options_filter(app):
    with app.app_context():
        api = EbayAPI()
        
        # Any (default)
        filters = {'buying_options': 'FIXED_PRICE|AUCTION'}
        assert 'buyingOptions' not in api._build_filter(filters)
    
        # Buy It Now
        filters = {'buying_options': 'FIXED_PRICE'}
        assert 'buyingOptions:{FIXED_PRICE}' in api._build_filter(filters)
    
        # Auction
        filters = {'buying_options': 'AUCTION'}
        assert 'buyingOptions:{AUCTION}' in api._build_filter(filters)

@pytest.mark.live  # Mark for live API tests
def test_real_buying_options(app):
    with app.app_context():
        api = EbayAPI(marketplace='EBAY_GB')
        
        # Test Buy It Now
        buy_it_now_items = api.search_new_items(
            "pokemon base set booster box 1st edition", 
            filters={'buying_options': 'FIXED_PRICE'}, 
        )
        assert len(buy_it_now_items) > 0
        for item in buy_it_now_items:
            assert 'price' in item
            assert isinstance(item['price'], float)
        
        # Test Auction
        auction_items = api.search_new_items(
            "pokemon base set booster box 1st edition", 
            filters={'buying_options': 'AUCTION'}, 
        )
        if len(auction_items) > 0:  # Auctions may not always be available
            for item in auction_items:
                assert 'price' in item
                # assert 'current_bid' in item  # If your parser extracts this
        
        # Test Any
        any_items = api.search_new_items("pokemon base set booster box 1st edition", filters={})
        assert len(any_items) >= len(buy_it_now_items) + (len(auction_items) if auction_items else 0)

#***********************
#Price Filtering Tests
#***********************

def test_response_price_format(app):
    with app.app_context():
        api = EbayAPI(marketplace='EBAY_US')
        items = api.search_new_items("pokemon base set booster box", filters={})
        print(items[0])
        assert len(items) > 0
        for item in items:
            assert 'price' in item
            assert isinstance(item['price'], float)

#***********************
#Scraping Ebay Tests
#***********************

def test_scrape_all_pages(app):
    with app.app_context():
        api = EbayAPI()
        items = api.search_all_pages("book")
        assert 200 <= len(items) <= 400
        assert len(set(item['ebay_id'] for item in items)) == len(items)

def test_search_new_items(app):
    with app.app_context():
        api = EbayAPI()
        items = api.search_new_items("book")
        assert len(items) <= 200

def test_search_raw_response(app):
    with app.app_context():
        api = EbayAPI("EBAY_GB")
        raw_response = api.search("iphone", limit=1)  # Get raw response
        items = api.parse_response(raw_response)  # Processed items
        
        print("\n=== Raw Response Type ===")
        print(raw_response)  # Should be dict
        
        print("\n=== Parsed Items Type ===")
        print(f"Type: {type(items)}")  # Should be list
        print(f"Length: {len(items)}")
        
        if items:
            print("\n=== First Item ===")
            print(items[0])
        else:
            print("No items found in parsed response")

#***********************
#Rate Limit Tests
#***********************

@pytest.mark.live
def test_rate_limit_check(app):
    with app.app_context():
        api = EbayAPI()
        
        # Get rate limits
        limits = api.check_rate_limits()
        
        # Validate response structure
        assert 'rateLimits' in limits, "Missing rateLimits key"
        assert len(limits['rateLimits']) > 0, "Empty rate limits array"
        
        # Find Browse API limits
        browse_limits = None
        for group in limits['rateLimits']:
            if group.get('apiContext') == 'buy' and group.get('apiName') == 'Browse':
                for resource in group.get('resources', []):
                    if resource.get('name') == 'buy.browse':
                        browse_limits = resource.get('rates', [{}])[0]
                        break
                if browse_limits:
                    break
        
        # Print Browse API details
        print("\nBrowse API Limits:")
        if browse_limits:
            print(f"Daily Limit: {browse_limits.get('limit')}")
            print(f"Remaining Calls: {browse_limits.get('remaining')}")
            print(f"Reset Time: {browse_limits.get('reset')}")
        else:
            print("Browse API limits not found in response")
        
        # Basic validation
        assert browse_limits, "Browse API limits missing"
        assert 'limit' in browse_limits, "Missing limit field"
        assert 'remaining' in browse_limits, "Missing remaining field"




