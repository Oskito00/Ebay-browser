import json
import requests
from datetime import datetime, timedelta, timezone
from flask import current_app
import time
from app.utils.parsing_helpers import parse_date
from app.utils.text_helpers import filter_items_by_keywords
from .constants import MARKETPLACE_IDS
import logging
from tenacity import retry, wait_exponential

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
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,  # Allow 10 simultaneous connections
            pool_maxsize=100      # Queue up to 100 requests
        )
        self.session.mount('https://', adapter)
    
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
    
    def raw_search(self, keywords, filters=None, limit=200, offset=0, sort_order=None):
        """Search with optional sorting"""
        # Initialize filters as empty dict if None
        filters = filters or {}

        # Gets a token if already present, if not generates a new one
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
            return self.raw_search(keywords, filters, limit, offset)
        response.raise_for_status()
        return response.json()
    
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10))
    def custom_search_query(self, keywords, filters=None, sort_order=None, max_pages=None, marketplace=None, search_for_sold=False, required_keywords=None, excluded_keywords=None):
        """
        The user can decide what they want to search for in this function
        Examples include: All items, only the first 200 items, the sold items (no longer active)
        """
        if marketplace:
            self.marketplace = marketplace

        returned_items = []
        pages_searched = 0
        offset = 0

        while (max_pages is None) or (pages_searched < max_pages):
            time.sleep(1)  # Add rate limiting
            
            raw_response = self.raw_search(
                keywords=keywords,
                filters=filters,
                limit=200,
                offset=offset,
                sort_order=sort_order
            )
            parsed_items = self.parse_response(raw_response)
            
            # Filter before appending
            filtered_batch = filter_items_by_keywords(parsed_items, required_keywords, excluded_keywords)
            returned_items.extend(filtered_batch)
            
            offset += len(parsed_items)
            pages_searched += 1

            # Break if last page
            if len(parsed_items) < 200:
                break
        
        # Remove duplicates while preserving order and handling null IDs
        seen_ids = set()
        unique_items = []
        for item in returned_items:
            item_id = item.get('ebay_id')
            if item_id:  # Only process items with an ID
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_items.append(item)
            else:
                # Optional: Keep items without IDs or skip them
                unique_items.append(item)  # Remove this line to exclude items without IDs
        
        print(f"Removed {len(returned_items) - len(unique_items)} duplicates")
        return unique_items
        
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
    
    def parse_response(self, response):
        items = []
        for item_data in response.get('itemSummaries', []):
            price_info = item_data.get('price', {})            
            # Base price handling
            base_price = {
                'value': float(price_info.get('value', 0)),
                'currency': price_info.get('currency', self.currency),
            }

            raw_buying_options = item_data.get('buyingOptions', [])
            is_auction = 'AUCTION' in raw_buying_options

            auction_data = {
            'bid_count': item_data.get('bidCount', 0),
            'current_bid': {
                'value': float(item_data.get('currentBidPrice', {}).get('value', 0)),
                'currency': item_data.get('currentBidPrice', {}).get('currency', self.currency)
            },
            'end_time': item_data.get('itemEndDate'),
            'marketplace_id': item_data.get('listingMarketplaceId')
            } if is_auction else None

            # Serialize complex fields
            serialized_categories = json.dumps({
                'ids': [cat['categoryId'] for cat in item_data.get('categories', [])],
                'names': [cat['categoryName'] for cat in item_data.get('categories', [])]
            })
            
            serialized_images = json.dumps({
                'main': item_data.get('image', {}).get('imageUrl'),
                'thumbnails': [img.get('imageUrl') for img in item_data.get('thumbnailImages', [])]
            })

            # Serialize auction details if they exist
            serialized_auction = json.dumps(auction_data) if auction_data else None

            items.append({
                'ebay_id': item_data.get('itemId'),
                'legacy_id': item_data.get('legacyItemId'),
                'title': item_data.get('title', 'No Title'),
                'price': base_price['value'],
                'currency': base_price['currency'],
                'url': item_data.get('itemWebUrl'),
                'image_url': item_data.get('image', {}).get('imageUrl'),
                'seller': item_data.get('seller', {}).get('username'),
                'seller_rating': item_data.get('seller', {}).get('feedbackPercentage'),
                'condition': item_data.get('condition'),
                'location': {
                    'country': item_data.get('itemLocation', {}).get('country'),
                    'postal_code': item_data.get('itemLocation', {}).get('postalCode')},
                'start_time': item_data.get(parse_date('itemCreationDate')),
                'end_time': parse_date(item_data.get('itemEndDate')),
                'buying_options': json.dumps(raw_buying_options),

                # New fields
                'auction_details': serialized_auction,
                'categories': serialized_categories,
                'marketplace': item_data.get('listingMarketplaceId'),
                'images': serialized_images,
                
            })
        return items
        
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

    

__all__ = ['EbayAPI']

