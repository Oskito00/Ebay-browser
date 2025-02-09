import os
from venv import logger
import requests
from datetime import datetime, timedelta
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
        self.token_expiry = 0
        self.marketplace = marketplace
        self.country_code = 'GB'
        self.client_id = os.getenv('EBAY_CLIENT_ID')
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.token_url = "https://api.ebay.com/identity/v1/oauth2/token"
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.headers = {
            'X-EBAY-C-MARKPLACE-ID': marketplace,
            'Accept-Language': 'en-GB',  # British English
            'Content-Language': 'en-GB', #TODO: make dynamic once it works
            'Authorization': f'Bearer {self._get_token()}',
            'Content-Type': 'application/json'
        }
        self.currency = 'GBP' if marketplace == 'EBAY_GB' else 'USD'
    
    def _token_needs_refresh(self):
        """Check if token needs refresh (60 second buffer)"""
        return time.time() >= self.token_expiry - 60


    def _get_token(self):
        if time.time() < self.token_expiry:
            return self.token
            
        # Client Credentials flow
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
        self.token_expiry = time.time() + token_data['expires_in'] - 60  # 1 min buffer
        return self.token

    def search(self, keywords, filters=None, limit=200, offset=0):
        logger.debug(
            f"Searching eBay {self.marketplace} marketplace "
            f"(Currency: {self.currency}, Country: {self.country_code})"
        )
        """Search with pagination support"""
        # Initialize filters as empty dict if None
        filters = filters or {}
        
        token = self._get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'X-EBAY-C-MARKPLACE-ID': self.marketplace,
            'X-EBAY-C-CURRENCY': self.currency,
            'Content-Type': 'application/json'
        }
        
        # Add country filter
        if 'country' not in filters:
            filters['country'] = MARKETPLACE_IDS[self.marketplace]['country']
        
        params = {
            'q': keywords,
            'filter': self._build_filter(filters),
            'sort': 'newlyListed',
            'limit': limit,
            'offset': offset
        }
        
        if self._token_needs_refresh():
            new_token = self._refresh_token()
            headers['Authorization'] = f'Bearer {new_token}'
        
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
        return {
            'total': response.json().get('total', 0),
            'itemSummaries': response.json().get('itemSummaries', [])
        }
    
    def _build_filter(self, filters):
        filter_parts = [
            'itemLocationCountry:GB',
            'priceCurrency:GBP',
            'sellerLocationCountry:GB',
            'priceCurrency:GBP'
        ]
        
        # Price range (if any)
        price_filter = []
        if filters.get('min_price'):
            price_filter.append(f"{filters['min_price']}..")
        if filters.get('max_price'):
            price_filter.append(f"..{filters['max_price']}")
        
        if price_filter:
            filter_parts.append(f'price:[{"".join(price_filter)}]')

        #TODO: add condition filter
        
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

    def parse_response(self, response, query_id):
        items = []
        for item_data in response.get('itemSummaries', []):
            image = item_data.get('image', {})
            price_info = item_data.get('price', {})
            items.append(Item(
                ebay_id=item_data.get('itemId', 'N/A'),
                title=item_data.get('title', 'No Title'),
                price=float(price_info.get('value', 0)),
                currency=price_info.get('currency', self.currency),
                url=item_data.get('itemWebUrl', '#'),
                image_url=image.get('imageUrl'),
                query_id=query_id,
                last_updated=datetime.utcnow()
            ))
        return items



def parse_ebay_response(response, query_id):
    items = []
    for item_data in response.get('itemSummaries', []):
        # Safely get image URL
        image = item_data.get('image', {})
        image_url = image.get('imageUrl') if image else None
        
        # Handle missing price
        price_data = item_data.get('price', {})
        try:
            price = float(price_data.get('value', 0))
        except (TypeError, ValueError):
            price = 0.0
        
        items.append(Item(
            ebay_id=item_data.get('itemId', 'N/A'),
            title=item_data.get('title', 'No Title'),
            price=price,
            url=item_data.get('itemWebUrl', '#'),
            image_url=image_url,
            query_id=query_id,
            last_updated=datetime.utcnow()
        ))
    return items 

# def execute_search(query):
#     try:
#         api = EbayAPI()
#         response = api.search(
#             keywords=query.keywords,
#             filters={
#                 'min_price': query.min_price,
#                 'max_price': query.max_price,
#                 'condition': query.conditions
#             }
#         )
        
#         # Process response
#         current_items = api.parse_response(response, query.id)
#         previous_items = get_previous_items(query)
#         new_items = identify_new_items(previous_items, current_items)
        
#         # Store results
#         save_results(query, current_items, new_items)
#         return new_items
        
#     except Exception as e:
#         logger.error(f"Search failed for query {query.id}: {str(e)}")
#         return []

def get_previous_items(query):
    if not query.results:
        return []
    return query.results[-1].items

def identify_new_items(previous, current):
    prev_ids = {item.ebay_id for item in previous}
    return [item for item in current if item.ebay_id not in prev_ids]

# def save_results(query, items, new_items):
#     result = Result(
#         query=query,
#         items=items,
#         new_items=new_items
#     )
#     db.session.add(result)
#     query.last_checked = datetime.utcnow()
#     db.session.commit()

def test_price_filter():
    api = EbayAPI()
    filters = {'min_price': 100}
    results = api.search("test", filters=filters)
    
    for item in results['itemSummaries']:
        price = float(item['price']['value'])
        currency = item['price']['currency']
        print(f"Item {item['itemId']}: {price} {currency}")
        assert price >= 100, f"Price {price} below min filter"

def validate_marketplace(marketplace):
    if marketplace not in MARKETPLACE_IDS.values():
        raise ValueError(f"Invalid marketplace. Valid options: {', '.join(MARKETPLACE_IDS.values())}")

__all__ = ['EbayAPI', 'parse_ebay_response']

