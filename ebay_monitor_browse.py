import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class EbayMonitor:
    def __init__(self):
        self.client_id = os.getenv('EBAY_CLIENT_ID')
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
            "X-EBAY-C-ENDUSERCTX": "contextualLocation=country=GB",
            "Content-Type": "application/json"
        }
        self.known_items_file = "known_items.json"
        self.item_details_file = "item_details.json"
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

    def search_items(self, keywords, filters=None, max_items=200):
        """Search for items using Browse API with filters"""
        try:
            all_items = []
            offset = 0
            limit = 200
            
            while True:
                # Combine filters into a single string
                filter_string = 'itemLocationCountry:GB,price:[150..],priceCurrency:GBP'
                
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
                
                if not results.get('itemSummaries'):
                    break
                    
                all_items.extend(results['itemSummaries'])
                offset += limit
                
                if max_items and offset >= max_items:
                    break
            
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
        
        # First run - silent collection
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
                # Print each item for inspection
                print("\nItem found:")
                print(f"Title: {item['title']}")
                print(f"Price: {item['price']['value']} {item['price']['currency']}")
                print(f"Location: {item.get('itemLocation', 'N/A')}")
                print(f"Link: {item['itemWebUrl']}")
            
            self.save_known_items()
            self.save_item_details()
            print(f"Initial items saved: {len(self.known_items)} items")
        
        first_run = False
        
        # Main monitoring loop
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

if __name__ == "__main__":
    # Check environment variables
    required_vars = [
        'EBAY_CLIENT_ID', 
        'EBAY_CLIENT_SECRET',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        exit(1)
    
    # Initialize monitor
    monitor = EbayMonitor()
    
    # Get user input
    print("\n=== eBay Item Monitor ===")
    search_term = input("Enter search term (default: iPhone 14 Pro): ").strip()
    if not search_term:
        search_term = "iPhone 14 Pro"
    
    try:
        check_interval = int(input("Enter check interval in seconds (default: 20): ").strip())
    except ValueError:
        check_interval = 20
    
    print(f"\nStarting monitor:")
    print(f"- Search term: {search_term}")
    print(f"- Check interval: {check_interval} seconds")
    print("\nPress Ctrl+C to stop monitoring\n")
    
    # Start monitoring
    monitor.monitor(search_term, check_interval)