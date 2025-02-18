import os
from venv import logger
import requests
from datetime import datetime, timedelta, timezone
from flask import current_app
import time
from .constants import CONDITION_IDS, MARKETPLACE_IDS
from app.models import Item
from app import db
import logging
import re
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

class EbayAPI:
    def __init__(self, marketplace='EBAY_GB'):
        self.token = None
        self.token_expiry = datetime.min.replace(tzinfo=timezone.utc)
        self.client_id = current_app.config.get('EBAY_CLIENT_ID')
        self.client_secret = current_app.config.get('EBAY_CLIENT_SECRET')
        
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set in the environment or config"
            )
        self.token_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.headers = {
            'X-EBAY-C-MARKPLACE-ID': marketplace,
            'X-EBAY-C-CURRENCY': MARKETPLACE_IDS[marketplace]['currency'],
            'Accept-Language': MARKETPLACE_IDS[marketplace]['language'],
            'Content-Language': MARKETPLACE_IDS[marketplace]['language'], 
            'Authorization': f'Bearer {self._get_token()}',
            'Content-Type': 'application/json'
        }
        self.marketplace = marketplace
        self.marketplace_config = MARKETPLACE_IDS.get(
            marketplace, 
            MARKETPLACE_IDS['EBAY_GB']
        )
        self.country_code = self.marketplace_config['location']
        self.currency = self.marketplace_config['currency']
        self._get_token()  # Fetch initial token
        self.session = requests.Session()
    
    def _token_needs_refresh(self):
        """Check if token needs refresh (60 second buffer)"""
        if not self.token:
            return True  # No token exists
        return datetime.now(timezone.utc) > (self.token_expiry - timedelta(seconds=60))

    def _get_token(self):
        """Main token acquisition method"""
        if not self._token_needs_refresh():
            return self.token
        
        # Refresh token if needed
        auth = (self.client_id, self.client_secret)
        data = {
            'grant_type': 'client_credentials',
            'scope': ' '.join([
                'https://api.ebay.com/oauth/api_scope',  # Public data
            ])
        }
        response = requests.post(
            self.token_url,
            auth=auth,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=data
        )
        response.raise_for_status()
        
        token_data = response.json()
        self.token = token_data['access_token']
        self.token_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=token_data['expires_in']
        )
        return self.token
    
    def check_rate_limits(self):
        """Check API rate limits using /rate_limit endpoint"""
        headers = {'Authorization': f'Bearer {self.token}'}
        
        response = requests.get(
            'https://api.ebay.com/developer/analytics/v1_beta/rate_limit',
            headers=headers
        )
        
        if response.status_code == 403:
            raise ValueError("Missing required scope")
        
        response.raise_for_status()
        return response.json()

    def search(self, keywords, filters=None, limit=200, offset=0, sort_order=None):
        """Search with optional sorting"""
        # Initialize filters as empty dict if None
        filters = filters or {}
        
        self._get_token()
        headers = {
            'Authorization': f'Bearer {self.token}',
            'X-EBAY-C-MARKETPLACE-ID': self.marketplace.replace('_', '-'),
            'X-EBAY-C-CURRENCY': self.currency,
            'Content-Language': self.marketplace_config['language'],
            'Accept-Language': self.marketplace_config['language'],
            'Content-Type': 'application/json'
        }
        
        params = {
            'q': keywords,
            'limit': limit,
            'offset': offset
        }
        
        # Add sort before filter
        if sort_order:
            params['sort'] = sort_order
        
        # Add filters if present
        if filters:
            params['filter'] = self._build_filter(filters)
        
        # Use persistent session
        response = self.session.get(
            f"{self.base_url}/item_summary/search",
            headers=headers,
            params=params
        )
        print(f"Request URL: {response.request.url}")
        
        if response.status_code == 429:
            sleep_time = int(response.headers.get('Retry-After', 60))
            time.sleep(sleep_time)
            return self.search(keywords, filters, limit, offset)
        response.raise_for_status()
        return response.json()
    
    def search_new_items(self, keywords, filters=None, marketplace=None, required_keywords=None, excluded_keywords=None):
        """
        Search first page of newly listed items
        :return: First 200 results (max eBay limit)
        :note: Pagination disabled for this method
        """
        if marketplace:
            self.marketplace = marketplace

        response = self.search(
            keywords=keywords,
            filters=filters,
            limit=200,
            offset=0,
            sort_order='newlyListed'
        )

        items = self.parse_response(response)

        # Filter items based on required and excluded keywords
        filtered_items = self._filter_items(items, required_keywords, excluded_keywords)

        return filtered_items
    
    def search_all_pages(self, keywords, filters=None, marketplace=None, required_keywords=None, excluded_keywords=None):
        """Search first two pages and return parsed items"""
        # Use marketplace if provided
        if marketplace:
            self.marketplace = marketplace
        
        all_items = []
        total = None
        offset = 0
        pages_scraped = 0
        max_pages = 2  # Maximum pages to scrape
        
        while pages_scraped < max_pages:
            time.sleep(current_app.config.get('EBAY_RATE_LIMIT', 1))  
            
            # Fetch and parse response
            raw_response = self.search(keywords, filters, limit=200, offset=offset)
            parsed_items = self.parse_response(raw_response)
            
            # First page initialization
            if total is None:
                total = raw_response.get('total', 0)
                if total == 0 or not parsed_items:
                    break
            
            # Store items and update counters
            all_items.extend(parsed_items)
            offset += len(parsed_items)
            pages_scraped += 1
            
            # Break early if no more items
            if len(parsed_items) < 200:
                break
        
        # Apply keyword filters
        filtered_items = self._filter_items(all_items, required_keywords, excluded_keywords)
        
        return filtered_items
    
    def _build_filter(self, filters):
        filter_parts = [
            f"itemLocationCountry:{filters.get('item_location', self.country_code)}",
            f"priceCurrency:{self.currency}"
        ]
        
        # Buying options filter
        buying_opt = filters.get('buying_options', 'FIXED_PRICE|AUCTION')
        if buying_opt != 'FIXED_PRICE|AUCTION':
            filter_parts.append(f"buyingOptions:{{{buying_opt}}}")
        
        # Condition filter
        condition = filters.get('condition')
        if condition in ['NEW', 'USED']:
            filter_parts.append(f"conditions:{{{condition}}}")
        
        # Handle price range correctly
        min_price = filters.get('min_price')
        max_price = filters.get('max_price')
        
        if min_price is not None or max_price is not None:
            price_filter = 'price:['
            if min_price is not None and max_price is not None:
                price_filter += f"{min_price}..{max_price}"
            elif min_price is not None:
                price_filter += f"{min_price}.."
            elif max_price is not None:
                price_filter += f"..{max_price}"
            price_filter += ']'
            filter_parts.append(price_filter)

        return ','.join(filter_parts)
    
    def _filter_items(self, items, required_keywords, excluded_keywords):
        # Convert None to empty string
        required = required_keywords or ''
        excluded = excluded_keywords or ''
        
        # Normalize inputs
        req_kws = {kw.strip().lower() for kw in required.split(',') if kw.strip()}
        excl_kws = {ekw.strip().lower() for ekw in excluded.split(',') if ekw.strip()}
        
        # Preprocess titles
        processed = []
        for item in items:
            title = item['title'].lower()
            words = set(title.split())
            processed.append((item, title, words))
        
        # Filter logic
        filtered = []
        for item, title, words in processed:
            # Required: all keywords present as whole words
            req_ok = all(
                re.search(rf'\b{re.escape(kw)}\b', title) 
                for kw in req_kws
            ) if req_kws else True
            
            # Excluded: none present as substrings
            excl_ok = not any(
                ekw in title
                for ekw in excl_kws
            ) if excl_kws else True
            
            if req_ok and excl_ok:
                filtered.append(item)
        
        return filtered

    def parse_response(self, response):
        items = []
        for item_data in response.get('itemSummaries', []):
            price_info = item_data.get('price', {})
            
            # Handle original price for non-US listings
            original_price = price_info.get('convertedFromValue')
            original_currency = price_info.get('convertedFromCurrency')
            
            # US listings don't have original prices
            if original_price is None:
                original_price = price_info.get('value')
                original_currency = self.currency  # USD for US marketplace
            
            items.append({
                'ebay_id': item_data.get('itemId'),
                'legacy_id': item_data.get('legacyItemId'),
                'title': item_data.get('title', 'No Title'),
                'price': float(price_info.get('value', 0)),
                'currency': price_info.get('currency', self.currency),
                'original_price': float(original_price) if original_price else None,
                'original_currency': original_currency,
                'url': item_data.get('itemWebUrl'),
                'image_url': item_data.get('image', {}).get('imageUrl'),
                'seller': item_data.get('seller', {}).get('username'),
                'seller_rating': item_data.get('seller', {}).get('feedbackPercentage'),
                'condition': item_data.get('condition'),
                'location': {
                    'country': item_data.get('itemLocation', {}).get('country'),
                    'postal_code': item_data.get('itemLocation', {}).get('postalCode')
                },
                'categories': [cat['categoryName'] for cat in item_data.get('categories', [])],
                'listing_date': item_data.get('itemCreationDate'),
            })
        return items

    def _parse_price(self, price_data, key='value'):
        try:
            return float(price_data.get(key, 0))
        except (TypeError, ValueError):
            return 0.0

    

__all__ = ['EbayAPI']

