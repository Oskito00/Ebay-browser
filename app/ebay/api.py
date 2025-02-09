import os
import requests
from datetime import datetime, timedelta
from flask import current_app
import time

class EbayAPI:
    def __init__(self):
        self.client_id = os.getenv('EBAY_CLIENT_ID')
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.token = None
        self.token_expiry = datetime.utcnow()
        
    def _get_auth_header(self):
        if datetime.utcnow() > self.token_expiry:
            self._refresh_token()
        return {'Authorization': f'Bearer {self.token}'}
    
    def _refresh_token(self):
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'scope': 'https://api.ebay.com/oauth/api_scope'
        }
        
        response = requests.post(
            url,
            headers=headers,
            data=data,
            auth=(self.client_id, self.client_secret)
        )
        token_data = response.json()
        self.token = token_data['access_token']
        self.token_expiry = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
    
    def search(self, keywords, filters=None, limit=200, offset=0):
        """Search with pagination support"""
        headers = self._get_auth_header()
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

def build_ebay_params(query):
    params = {
        'keywords': query.keywords,
        'sortOrder': 'PricePlusShippingLowest',
        'limit': query.limit
    }
    
    if query.filters:
        if 'min_price' in query.filters:
            params['minPrice'] = query.filters['min_price']
        if 'max_price' in query.filters:
            params['maxPrice'] = query.filters['max_price']
        if 'condition' in query.filters:
            params['itemFilter'] = [{
                'name': 'Condition',
                'value': query.filters['condition']
            }]
    
    return params 