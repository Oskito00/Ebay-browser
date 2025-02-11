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
            'Accept-Language': 'en-GB',  # TODO: This might give errors when I switch to country that doesn't speak english
            'Content-Language': 'en-GB', #TODO: make dynamic once it works
            'Authorization': f'Bearer {self._get_token()}',
            'Content-Type': 'application/json'
        }
        self.marketplace = marketplace
        self.country_code = MARKETPLACE_IDS[marketplace]['location']
        self.currency = MARKETPLACE_IDS[marketplace]['currency']
        self._get_token()  # Fetch initial token
    
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
        response = requests.post(
            self.token_url,
            auth=auth,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'client_credentials',
                'scope': 'https://api.ebay.com/oauth/api_scope'
            }
        )
        response.raise_for_status()
        
        token_data = response.json()
        self.token = token_data['access_token']
        self.token_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=token_data['expires_in']
        )
        return self.token

    def search(self, keywords, filters=None, limit=200, offset=0):
        """Search with pagination support"""
        # Initialize filters as empty dict if None
        filters = filters or {}
        
        self._get_token()
        headers = {
            'Authorization': f'Bearer {self.token}',
            'X-EBAY-C-MARKPLACE-ID': self.marketplace,
            'X-EBAY-C-CURRENCY': self.currency,
            'Content-Type': 'application/json'
        }
        
        params = {
            'q': keywords,
            'filter': self._build_filter(filters),
            'sort': 'newlyListed',
            'limit': limit,
            'offset': offset
        }
        
        response = requests.get(
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
    
    def search_all_pages(self, keywords, filters=None, marketplace=None):
        """Search all pages and return parsed items as dictionaries"""
        # Use marketplace if provided
        if marketplace:
            self.marketplace = marketplace
        
        all_items = []
        total = None
        offset = 0
        
        while True:
            # Add dynamic rate limiting
            time.sleep(current_app.config.get('EBAY_RATE_LIMIT', 1))  
            
            # Fetch raw API response
            raw_response = self.search(keywords, filters, limit=200, offset=offset)
            
            # Parse items immediately
            parsed_items = self.parse_response(raw_response)
            # First page initialization
            if total is None:
                total = raw_response.get('total', 0)
                if total == 0 or not parsed_items:
                    break
            
            # Store parsed items
            all_items.extend(parsed_items)
            
            # Update offset using parsed items count
            offset += len(parsed_items)
            
            # Break conditions
            if len(parsed_items) < 200:
                break
            if offset >= total:
                break
        
        return all_items
    
    def _build_filter(self, filters):
        filter_parts = [
        ]

        filter_parts.append(f"itemLocationCountry:{filters.get('item_location', self.country_code)}")
        filter_parts.append(f"priceCurrency:{self.currency}")


        
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

    def build_ebay_params(self, query):
        params = {
            'q': query.keywords,
            'sort': 'price',
            'limit': query.limit,
            'filter': []
        }
        
        if query.filters:
            # Price range
            price_parts = []
            if 'min_price' in query.filters:
                price_parts.append(f"{query.filters['min_price']}")
            else:
                price_parts.append("")  # Empty min price
            
            if 'max_price' in query.filters:
                price_parts.append(f"{query.filters['max_price']}")
            else:
                price_parts.append("")  # Empty max price
            
            price_filter = f"price:[{'..'.join(price_parts)}]"
            if any(price_parts):
                params['filter'].append(price_filter)
            
            # Condition
            if 'condition' in query.filters:
                condition_ids = [CONDITION_IDS[c] for c in query.filters['condition']]
                params['filter'].append(f"conditionIds:{{{','.join(condition_ids)}}}")
            
            # Join filters
            if params['filter']:
                params['filter'] = ','.join(params['filter'])
            else:
                del params['filter']
        
        # After building filters
        if not params['filter']:
            del params['filter']
        
        return params 

    def parse_response(self, response):
        items = []
        for item_data in response.get('itemSummaries', []):
            price_info = item_data.get('price', {})
            
            # Handle original price for non-US listings
            original_price = price_info.get('convertedFromValue')
            original_currency = price_info.get('convertedFromCurrency')
            
            # US listings don't have converted prices
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

__all__ = ['EbayAPI', 'parse_ebay_response']

