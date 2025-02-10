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
        self.client_id = os.getenv('EBAY_CLIENT_ID')
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET')
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
        return {
            'total': response.json().get('total', 0),
            'itemSummaries': response.json().get('itemSummaries', [])
        }
    
    def _build_filter(self, filters):
        filter_parts = [
        ]

        filter_parts.append(f"itemLocationCountry:{filters.get('item_location', self.country_code)}")
        filter_parts.append(f"currency:{self.currency}")


        
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


def validate_marketplace(marketplace):
    if marketplace not in MARKETPLACE_IDS.values():
        raise ValueError(f"Invalid marketplace. Valid options: {', '.join(MARKETPLACE_IDS.values())}")

__all__ = ['EbayAPI', 'parse_ebay_response']

