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
        assert len(filtered) == 2
        assert all('base' not in item['title'].lower() for item in filtered)
    
        # Test multiple exclusions
        filtered = mock_ebay_api._filter_items(
        mock_items,
        required_keywords='',
        excluded_keywords='base,shadowless'
        )
        assert len(filtered) == 1

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
