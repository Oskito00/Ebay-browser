import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class EbayMonitor:
    def __init__(self, instance_name="default"):
        self.client_id = os.getenv('EBAY_CLIENT_ID')
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.token_timestamp = time.time()
        self.token_expiry = 7200  # 2 hours in seconds
        self.headers = {
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
            "X-EBAY-C-ENDUSERCTX": "contextualLocation=country=GB",
            "Content-Type": "application/json"
        }
        self.instance_name = instance_name
        self.known_items_file = f"known_items_{instance_name}.json"
        self.item_details_file = f"item_details_{instance_name}.json"
        self.known_items = self.load_known_items()
        self.item_details = self.load_item_details()
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
    def _get_access_token(self):
        """Get OAuth token from eBay"""
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        response = requests.post(
            url,
            headers=headers,
            data=data,
            auth=(self.client_id, self.client_secret)
        )
        return response.json()["access_token"]

    def _refresh_token_if_needed(self):
        """Check if token needs refresh and update if necessary"""
        if time.time() - self.token_timestamp >= self.token_expiry:
            print("Refreshing OAuth token...")
            self.token_timestamp = time.time()
            return self._get_access_token()
        return None

    def search_items(self, keywords, filters=None, max_items=None):
        """Search for items using Browse API with filters"""
        try:
            # Refresh token if needed
            new_token = self._refresh_token_if_needed()
            if new_token:
                self.headers["Authorization"] = f"Bearer {new_token}"
            else:
                self.headers["Authorization"] = f"Bearer {self._get_access_token()}"

            all_items = []
            offset = 0
            limit = 200
            
            # Construct price filter based on provided values
            filter_parts = ['itemLocationCountry:GB']
            
            # Add price filter if specified
            if filters and (filters.get('min_price') or filters.get('max_price')):
                price_filter = 'price:['
                if filters.get('min_price') and filters.get('max_price'):
                    price_filter += f"{filters['min_price']}..{filters['max_price']}"
                elif filters.get('min_price'):
                    price_filter += f"{filters['min_price']}.."
                elif filters.get('max_price'):
                    price_filter += f"..{filters['max_price']}"
                price_filter += ']'
                filter_parts.append(price_filter)
                filter_parts.append('priceCurrency:GBP')
            
            # Join all filters
            filter_string = ','.join(filter_parts)
            
            while True:
                params = {
                    'q': keywords,
                    'filter': filter_string,
                    'sort': 'newlyListed',
                    'limit': str(limit),
                    'offset': str(offset)
                }
                
                url = f"{self.base_url}/item_summary/search"
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params
                )
                
                print(f"Request URL: {url}?q={params['q']}&filter={params['filter']}&sort={params['sort']}&limit={params['limit']}&offset={params['offset']}")
                
                results = response.json()
                total_items = results.get('total', 0)
                print(f"Total items across all pages: {total_items}")
                
                if not results.get('itemSummaries'):
                    break
                    
                # Get required keywords from filters
                required_keywords = filters.get('required_keywords') if filters else None
                
                # Define exclusion keywords
                exclusion_keywords = []
                
                if required_keywords:
                    # Post-process to filter items that contain required keywords but not exclusion keywords
                    filtered_items = [
                        item for item in results['itemSummaries']
                        if any(keyword.lower() in item['title'].lower() for keyword in required_keywords)
                        and not any(ex_keyword.lower() in item['title'].lower() for ex_keyword in exclusion_keywords)
                    ]
                else:
                    filtered_items = results['itemSummaries']

                print(f"Found {len(filtered_items)} items matching required keywords: {required_keywords}")
                print(f"(Excluded items containing: {exclusion_keywords})")
                all_items.extend(filtered_items)
                offset += limit
                
                if offset >= total_items:
                    print(f"Reached end of available items ({total_items} total)")
                    break
            
            print(f"Total relevant items collected: {len(all_items)}")
            return {"itemSummaries": all_items}
        except Exception as e:
            print(f"Search error: {str(e)}")
            return None

    def send_notification(self, item):
        """Send Telegram notification for new item"""
        message = (
            f"🔔 *New eBay Item Found!*\n\n"
            f"📦 *Title:* {item['title']}\n"
            f"💰 *Price:* {item['price']['value']} {item['price']['currency']}\n"
            f"📝 *Condition:* {item.get('condition', 'N/A')}\n"
            f"🔗 [View Item]({item['itemWebUrl']})"
        )
        
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                }
            )
        except Exception as e:
            print(f"Failed to send Telegram notification: {str(e)}")

    def save_known_items(self):
        """Save known items to JSON file"""
        with open(self.known_items_file, 'w') as f:
            json.dump(list(self.known_items), f)

    def load_known_items(self):
        """Load known items from JSON file"""
        try:
            with open(self.known_items_file, 'r') as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def load_item_details(self):
        """Load item details from JSON file"""
        try:
            with open(self.item_details_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_item_details(self):
        """Save item details to JSON file"""
        with open(self.item_details_file, 'w') as f:
            json.dump(self.item_details, f, indent=2)

    def monitor(self, keywords, check_interval=60, filters=None):
        """Monitor for new items with filters"""
        print(f"Starting monitor for: {keywords}")
        print(f"Checking every {check_interval} seconds")
        if filters:
            print("Filters applied:", filters)
        
        # First run - silent collecting get all the items and store them in a json file
        first_run = True
        results = self.search_items(keywords, filters)
        if results and 'itemSummaries' in results:
            items = results['itemSummaries']
            print(f"\nFirst run: Found {len(items)} items")
            for item in items:
                item_id = item['itemId']
                self.known_items.add(item_id)
                self.item_details[item_id] = {
                    'title': item['title'],
                    'price': item['price'],
                    'condition': item.get('condition', 'N/A'),
                    'url': item['itemWebUrl'],
                    'location': item.get('itemLocation', 'N/A')
                }
            
            self.save_known_items()
            self.save_item_details()
            print(f"Initial items saved: {len(self.known_items)} items")
        
        first_run = False
        
        # Main monitoring loop - notify when a new item is found
        while True:
            try:
                print(f"\nChecking eBay at {datetime.now()}")
                results = self.search_items(keywords, filters)
                
                if results and 'itemSummaries' in results:
                    items = results['itemSummaries']
                    print(f"Found {len(items)} items")
                    
                    for item in items:
                        item_id = item['itemId']
                        
                        if item_id not in self.known_items:
                            print("\n=== NEW ITEM FOUND ===")
                            print(f"Title: {item['title']}")
                            print(f"Price: {item['price']['value']} {item['price']['currency']}")
                            print(f"Location: {item.get('itemLocation', 'N/A')}")
                            print(f"Link: {item['itemWebUrl']}")
                            print("=====================")
                            
                            if not first_run:
                                self.send_notification(item)
                            
                            self.known_items.add(item_id)
                            self.item_details[item_id] = {
                                'title': item['title'],
                                'price': item['price'],
                                'condition': item.get('condition', 'N/A'),
                                'url': item['itemWebUrl'],
                                'location': item.get('itemLocation', 'N/A')
                            }
                            self.save_known_items()
                            self.save_item_details()
                
                    print(f"Total known items: {len(self.known_items)}")
                
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"Error occurred: {str(e)}")
                time.sleep(check_interval)