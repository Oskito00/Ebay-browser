import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv
import threading
from urllib.parse import urlencode
import traceback

load_dotenv()

class EbayMonitor:
    def __init__(self):
        self.queries = {}  # {query_id: {config}}
        self.known_items = {}  # {query_id: set()}
        self.active = False
        self.lock = threading.Lock()
        self._load_queries()
        
        # Existing auth setup
        self.client_id = os.getenv('EBAY_CLIENT_ID')
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.headers = {
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
            "Content-Type": "application/json"
        }
        self._refresh_token()

        # Telegram setup
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # Thread verification
        self.monitor_thread = threading.Thread(
            target=self.monitor_loop,
            name="EbayMonitorThread",
            daemon=True
        )
        self.monitor_thread.start()
        print(f"Thread started - Alive: {self.monitor_thread.is_alive()}")
        print(f"Active threads: {threading.enumerate()}")

        # Add to class __init__
        self.last_request_time = time.time()

    def _get_access_token(self):
        try:
            print("\n=== Attempting to get eBay access token ===")
            url = "https://api.ebay.com/identity/v1/oauth2/token"
            response = requests.post(
                url,
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "scope": "https://api.ebay.com/oauth/api_scope"
                }
            )
            response.raise_for_status()
            token_data = response.json()
            self.headers["Authorization"] = f"Bearer {token_data['access_token']}"
            print("Successfully obtained access token")
            return token_data["access_token"]
        
        except Exception as e:
            print(f"\n!!! Token acquisition failed !!!")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            if hasattr(e, 'response'):
                print(f"Response Status: {e.response.status_code}")
                print(f"Response Body: {e.response.text}")
            raise

    def _refresh_token_if_needed(self):
        """Check if token needs refresh and update if necessary"""
        if time.time() - self.token_timestamp >= self.token_expiry:
            print("Refreshing OAuth token...")
            self.token_timestamp = time.time()
            return self._get_access_token()
        return None

    def search_items(self, keywords, filters=None):
        all_items = []
        offset = 0
        total_pages = 1  # Initialize with at least one page
        
        try:
            while offset < total_pages * 100:  # 100 items per page
                params = {
                    'q': keywords,
                    'limit': 100,
                    'offset': offset,
                    'filter': self._build_filter_string(filters)
                }
                
                print(f"Fetching page {(offset//100)+1} (offset: {offset})")
                response = requests.get(
                    "https://api.ebay.com/buy/browse/v1/item_summary/search",
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                all_items.extend(data.get('itemSummaries', []))
                
                # Get total pages
                total = data.get('total', 0)
                total_pages = max(total_pages, (total // 100) + 1)
                
                # Break if no more items
                if len(data.get('itemSummaries', [])) < 100:
                    break
                    
                offset += 100
                time.sleep(1)  # Rate limit
                
                print(f"Page {(offset//100)+1}: Found {len(data.get('itemSummaries', []))} items")
                
            return {'itemSummaries': all_items}
            
        except Exception as e:
            print(f"Search failed: {str(e)}")
            return None

    def send_notification(self, item):
        if not self.telegram_token or not self.telegram_chat_id:
            print("Telegram credentials not configured")
            return
        
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
                },
                timeout=10
            )
        except Exception as e:
            print(f"Telegram notification failed: {str(e)}")

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

    def add_query(self, query_id, keywords, filters=None):
        # Add validation
        if filters:
            min_price = filters.get('min_price')
            max_price = filters.get('max_price')
            if min_price and max_price and float(min_price) > float(max_price):
                raise ValueError("Minimum price cannot exceed maximum price")
        
        with self.lock:
            self.queries[query_id] = {
                'keywords': keywords,
                'filters': filters or {},
                'first_run': True,
                'created': datetime.now().isoformat()
            }
            self.known_items[query_id] = set()
            self._save_queries()

    def remove_query(self, query_id):
        with self.lock:
            if query_id in self.queries:
                del self.queries[query_id]
            if query_id in self.known_items:
                del self.known_items[query_id]
            self._save_queries()

    def _save_queries(self):
        data = {
            'active': self.active,
            'queries': self.queries,
            'known_items': {k: list(v) for k, v in self.known_items.items()}
        }
        with open('queries.json', 'w') as f:
            json.dump(data, f)

    def _load_queries(self):
        try:
            with open('queries.json', 'r') as f:
                data = json.load(f)
                self.active = data.get('active', False)
                self.queries = data.get('queries', {})
                
                # Ensure existing queries have first_run set to False
                for qid in self.queries:
                    if 'first_run' not in self.queries[qid]:
                        self.queries[qid]['first_run'] = False
                    
                self.known_items = {k: set(v) for k,v in data.get('known_items', {}).items()}
        except FileNotFoundError:
            pass

    def monitor_loop(self):
        print("\n=== Monitoring thread started ===")
        while True:
            try:
                print(f"\n[Monitor Loop] Active: {self.active}")
                if self.active:
                    print("[Monitor Loop] Starting check cycle")
                    with self.lock:
                        queries = list(self.queries.items())
                    
                    if not queries:
                        print("[Monitor Loop] No active queries to check")
                        
                    for query_id, config in queries:
                        print(f"\n[Checking Query] ID: {query_id}")
                        print(f"Keywords: {config['keywords']}")
                        print(f"Filters: {config.get('filters', {})}")
                        self._check_query(query_id, config)
                    
                    print("[Monitor Loop] Cycle completed")
                    time.sleep(60)
                else:
                    print("[Monitor Loop] Inactive, sleeping...")
                    time.sleep(5)
                    
            except Exception as e:
                print(f"\n!!! Monitor loop crashed !!!")
                print(f"Error Type: {type(e).__name__}")
                print(f"Error Message: {str(e)}")
                print(traceback.format_exc())
                time.sleep(30)

    def _check_query(self, query_id, config):
        try:
            print(f"\n=== Checking query: {config['keywords']} ===")
            results = self.search_items(config['keywords'], config.get('filters'))
            
            if not results:
                return
            
            items = results.get('itemSummaries', [])
            new_items = [
                item for item in items
                if item['itemId'] not in self.known_items.get(query_id, set())
            ]
            
            if config['first_run']:
                print("First run - recording items without notification")
                with self.lock:
                    self.known_items[query_id].update(item['itemId'] for item in items)
                    self.queries[query_id]['first_run'] = False
                    self._save_queries()
            else:
                if new_items:
                    print(f"New items found: {len(new_items)}")
                    self._send_notifications(query_id, new_items)
                    with self.lock:
                        self.known_items[query_id].update(item['itemId'] for item in new_items)
                        self._save_queries()
                    
        except Exception as e:
            print(f"Query check failed: {str(e)}")

    def _refresh_token(self):
        """Refresh token and update headers"""
        self.token_timestamp = time.time()
        self.token_expiry = 7200  # 2 hours in seconds
        self.headers["Authorization"] = f"Bearer {self._get_access_token()}"

    def _build_filter_string(self, filters):
        """Construct eBay API filter string from our filters"""
        filter_parts = []
        
        # Price filter
        price_filter = []
        if filters:
            if filters.get('min_price'):
                price_filter.append(f"{filters['min_price']}")
            else:
                price_filter.append("")
            
            if filters.get('max_price'):
                price_filter.append(f"{filters['max_price']}")
            else:
                price_filter.append("")
        
        if any(price_filter):
            filter_parts.append(f"price:[{'..'.join(price_filter)}]")
        
        # Condition filter
        if filters and filters.get('condition'):
            filter_parts.append(f"conditionIds:{{{filters['condition']}}}")
        
        # Location and currency
        filter_parts.append("itemLocationCountry:GB")
        filter_parts.append("priceCurrency:GBP")
        
        return ','.join(filter_parts)

    def _send_notifications(self, query_id, items):
        try:
            if not self.telegram_token or not self.telegram_chat_id:
                print("Telegram credentials missing - skipping notifications")
                return
            
            print(f"Sending notifications for {len(items)} items")
            
            # Get query details
            query = self.queries[query_id]
            base_url = "https://www.ebay.co.uk/itm/"
            
            for item in items:
                try:
                    message = (
                        f"🏷️ *New Item Alert* 🚨\n"
                        f"*Title*: {item['title']}\n"
                        f"*Price*: £{item['price']['value']}\n"
                        f"*Condition*: {item.get('condition', 'N/A')}\n"
                        f"[View Item]({base_url}{item['itemId']})"
                    )
                    
                    # Send Telegram message
                    requests.post(
                        f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                        json={
                            'chat_id': self.telegram_chat_id,
                            'text': message,
                            'parse_mode': 'Markdown'
                        }
                    )
                    print(f"Notification sent for item {item['itemId']}")
                    
                except Exception as e:
                    print(f"Failed to send notification: {str(e)}")
        except Exception as e:
            print(f"Notification error: {str(e)}")

    def _update_rate_limit(self):
        time_since_last = time.time() - self.last_request_time
        if time_since_last < 0.5:  # 2 requests per second
            time.sleep(0.5 - time_since_last)
        self.last_request_time = time.time()