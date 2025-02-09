import os
import requests
from datetime import datetime, timedelta
from flask import current_app
import time
from .constants import CONDITION_IDS

class EbayAPI:
    def __init__(self):
        self.client_id = os.getenv('EBAY_CLIENT_ID')
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.token_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.token = None
        self.token_expiry = 0
        
    def _get_token(self):
        if time.time() < self.token_expiry:
            return self.token
            
        auth = (self.client_id, self.client_secret)
        data = {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'}
        response = requests.post(self.token_url, auth=auth, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.token = token_data['access_token']
        self.token_expiry = time.time() + token_data['expires_in'] - 60  # 1 min buffer
        return self.token

    def search(self, keywords, filters=None, limit=200, offset=0):
        """Search with pagination support"""
        token = self._get_token()
        headers = {'Authorization': f'Bearer {token}'}
        headers.update({
            'X-EBAY-C-MARKETPLACE-ID': 'EBAY_GB',
            'Content-Type': 'application/json'
        })
        
        params = {
            'q': keywords,
            'sort': 'newlyListed',
            'limit': limit,
            'offset': offset,
            'fieldgroups': 'FULL'
        }
        
        if filters:
            filter_str = self._build_filter(filters)
            if filter_str:
                params['filter'] = filter_str
        
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(
                    f"{self.base_url}/item_summary/search",
                    headers=headers,
                    params=params
                )
                if response.status_code == 429:
                    sleep_time = int(response.headers.get('Retry-After', 60))
                    time.sleep(sleep_time)
                    continue
                response.raise_for_status()
                return {
                    'total': response.json().get('total', 0),
                    'itemSummaries': response.json().get('itemSummaries', [])
                }
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    continue
                raise
    
    def _build_filter(self, filters):
        """Convert filters to eBay API filter string"""
        filter_parts = []
        
        # Price range
        if 'min_price' in filters or 'max_price' in filters:
            price_filter = 'price:['
            if 'min_price' in filters:
                price_filter += f"{filters['min_price']}"
            price_filter += '..'
            if 'max_price' in filters:
                price_filter += f"{filters['max_price']}"
            price_filter += ']'
            filter_parts.append(price_filter)
        
        # Condition
        if 'condition' in filters:
            filter_parts.append(f"conditionIds:{{{','.join(filters['condition'])}}}")
        
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