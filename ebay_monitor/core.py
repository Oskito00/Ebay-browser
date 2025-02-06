import os
import json
import time
import requests
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class EbayMonitor:
    def __init__(self):
        self.queries = self._load_data("queries.json", {})
        self.known_items = self._load_data("known_items.json", {})
        self.active_queries = {}
        self.lock = threading.Lock()
        self.running = False
        self.token = None
        self.token_expiry = 0
        self.query_status = {}  # Track initialization status
        
        # eBay API config
        self.client_id = os.getenv("EBAY_CLIENT_ID")
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET")
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.headers = {
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
            "Content-Type": "application/json"
        }
        self._refresh_token()  # Get initial token
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _refresh_token(self):
        """Get new OAuth token with proper error handling"""
        if time.time() < self.token_expiry - 60:  # 60-second buffer
            return
        
        print("Refreshing eBay token...")
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        auth = (self.client_id, self.client_secret)
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        try:
            response = requests.post(
                url,
                auth=auth,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()
            
            self.token = token_data["access_token"]
            self.token_expiry = time.time() + token_data["expires_in"]
            self.headers["Authorization"] = f"Bearer {self.token}"
            
        except Exception as e:
            print(f"Token refresh failed: {str(e)}")
            raise

    def _load_data(self, filename, default):
        """Load JSON data with locking"""
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def _save_data(self, filename, data):
        """Save JSON data with locking"""
        with self.lock:
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)

    def add_query(self, query_id, keywords, filters=None):
        """Add new search query"""
        with self.lock:
            self.queries[query_id] = {
                "keywords": keywords,
                "filters": filters or {},
                "created": datetime.now().isoformat()
            }
            self.known_items[query_id] = []
            self._save_data("queries.json", self.queries)
            self._save_data("known_items.json", self.known_items)
            
        # Run initial population in background
        threading.Thread(target=self._initial_population, args=(query_id,), daemon=True).start()

    def _initial_population(self, query_id):
        """Silently populate known items with status updates"""
        self.query_status[query_id] = "Starting initial search..."
        print(f"Initial population started for {query_id}")
        
        try:
            config = self.queries[query_id]
            items = self._search(
                config["keywords"],
                config["filters"].get("min_price"),
                config["filters"].get("max_price")
            )
            
            self.query_status[query_id] = f"Found {len(items)} initial items"
            
            with self.lock:
                self.known_items[query_id] = [item["itemId"] for item in items]
                self._save_data("known_items.json", self.known_items)
                self.active_queries[query_id] = True
                
            self.query_status[query_id] = "Monitoring active"
            print(f"Initial population completed for {query_id}")
            
        except Exception as e:
            self.query_status[query_id] = f"Error: {str(e)}"
            print(f"Initial population failed: {str(e)}")
            raise

    def _search(self, keywords, min_price=None, max_price=None):
        """Search with proper error handling and pagination"""
        self._refresh_token()
        
        all_items = []
        offset = 0
        limit = 200
        
        # Build price filter
        price_filter = []
        if min_price or max_price:
            price_range = []
            if min_price:
                price_range.append(str(min_price))
            if max_price:
                price_range.append(str(max_price))
            
            price_filter.append(f"price:[{'..'.join(price_range)}]")
            price_filter.append("priceCurrency:GBP")  # Critical fix
        
        while True:
            try:
                params = {
                    "q": keywords,
                    "filter": ",".join(price_filter),
                    "limit": limit,
                    "offset": offset,
                    "sort": "newlyListed"  # Important for monitoring
                }
                
                response = requests.get(
                    f"{self.base_url}/item_summary/search",
                    headers=self.headers,
                    params=params,
                    timeout=30  # Add timeout
                )
                response.raise_for_status()
                
                data = response.json()
                items = data.get("itemSummaries", [])
                all_items.extend(items)
                
                if len(items) < limit:
                    break
                    
                offset += limit
                
            except requests.HTTPError as e:
                if e.response.status_code == 401:  # Token expired
                    self._refresh_token()
                    continue
                raise
                
            except Exception as e:
                print(f"Search error: {str(e)}")
                break
                
        return all_items

    def _monitor_loop(self):
        """Main monitoring loop"""
        self.running = True
        while self.running:
            try:
                # Copy to prevent thread issues
                active_queries = list(self.active_queries.keys())
                
                for query_id in active_queries:
                    self._check_query(query_id)
                    
                time.sleep(60)  # Check every 60 seconds
                
            except Exception as e:
                print(f"Monitoring error: {str(e)}")
                time.sleep(30)

    def _check_query(self, query_id):
        """Check for new items in a query"""
        try:
            config = self.queries[query_id]
            items = self._search(
                config["keywords"],
                config["filters"].get("min_price"),
                config["filters"].get("max_price")
            )
            
            new_items = [
                item for item in items
                if item["itemId"] not in self.known_items[query_id]
            ]
            
            if new_items:
                self._handle_new_items(query_id, new_items)
                with self.lock:
                    self.known_items[query_id].extend([item["itemId"] for item in new_items])
                    self._save_data("known_items.json", self.known_items)
                    
        except Exception as e:
            print(f"Query check failed for {query_id}: {str(e)}")

    def _handle_new_items(self, query_id, items):
        """Send notifications for new items"""
        for item in items:
            print(f"New item found in {query_id}: {item['title']}")
            self._send_telegram(
                f"New listing: {item['title']}\n"
                f"Price: {item['price']['value']} {item['price']['currency']}\n"
                f"Link: {item['itemWebUrl']}"
            )

    def _send_telegram(self, message):
        """Send Telegram notification"""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if token and chat_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": message}
                )
            except Exception as e:
                print(f"Telegram send failed: {str(e)}")

    def remove_query(self, query_id):
        """Remove a query and its data"""
        with self.lock:
            self.queries.pop(query_id, None)
            self.known_items.pop(query_id, None)
            self.active_queries.pop(query_id, None)
            self._save_data("queries.json", self.queries)
            self._save_data("known_items.json", self.known_items)

    def stop(self):
        """Stop monitoring"""
        self.running = False
        self.monitor_thread.join()