import requests
import time
import os
import base64
from dotenv import load_dotenv

load_dotenv()  # Add this at the top

MARKETPLACES = {
    'EBAY-US': {'code': 'EBAY-US', 'currency': 'USD', 'domain': 'ebay.com'},
    'EBAY-GB': {'code': 'EBAY-GB', 'currency': 'GBP', 'domain': 'ebay.co.uk'},
    'EBAY-DE': {'code': 'EBAY-DE', 'currency': 'EUR', 'domain': 'ebay.de'}
}

class EbayAPI:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id or os.getenv('EBAY_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('EBAY_CLIENT_SECRET')
        self.base_url = os.getenv('EBAY_API_URL')
        self.access_token = None
        self.token_expiry = None
        
        if not all([self.client_id, self.client_secret, self.base_url]):
            raise ValueError("Missing Ebay API credentials in environment")
            
        self._authenticate()

    def _authenticate(self):
        auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth}'
        }
        
        data = {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'}
        
        response = requests.post(auth_url, headers=headers, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        self.token_expiry = time.time() + token_data['expires_in'] - 60  # 1 minute buffer
        
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def _build_filter(self, filters):
        # Implementation of _build_filter method
        pass

    def search(self, keywords, marketplace, filters=None):
        if time.time() > self.token_expiry:
            self._authenticate()
            
        items = []
        offset = 0
        limit = 100
        
        while True:
            params = {
                'q': keywords,
                'limit': limit,
                'offset': offset,
                'X-EBAY-C-MARKPLACE-ID': marketplace
            }
            
            if filters:
                filter_str = self._build_filter(filters)
                if filter_str:
                    params['filter'] = filter_str
                    
            response = requests.get(f"{self.base_url}/item_summary/search", 
                                  params=params, 
                                  headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            items.extend(data.get('itemSummaries', []))
            
            # Correct pagination logic
            if offset + limit >= data.get('total', 0):
                break
                
            offset += limit
            time.sleep(1)
            
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining < 5:
                    time.sleep(60 / remaining)
            
        return {'itemSummaries': items} 