import os
import requests
from datetime import datetime, timedelta

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
    
    def search_items(self, keywords, filters=None):
        headers = self._get_auth_header()
        headers.update({
            'X-EBAY-C-MARKETPLACE-ID': 'EBAY_GB',
            'Content-Type': 'application/json'
        })
        
        params = {
            'q': keywords,
            'sort': 'newlyListed',
            'limit': 200
        }
        
        # Add filters
        if filters:
            filter_str = self._build_filter(filters)
            if filter_str:
                params['filter'] = filter_str
        
        response = requests.get(
            f"{self.base_url}/item_summary/search",
            headers=headers,
            params=params
        )
        
        return response.json()
    
    def _build_filter(self, filters):
        filter_parts = []
        
        # Price filter
        if filters.get('min_price') or filters.get('max_price'):
            price_filter = 'price:['
            if filters.get('min_price'):
                price_filter += f"{filters['min_price']}.."
            if filters.get('max_price'):
                price_filter += f"{filters['max_price']}"
            price_filter += ']'
            filter_parts.append(price_filter)
        
        # Condition filter
        if filters.get('condition'):
            filter_parts.append(f"conditionIds:{{{','.join(filters['condition'])}}}")
        
        return ','.join(filter_parts) 