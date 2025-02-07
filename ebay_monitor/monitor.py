import json
import os
import time
import threading
import requests
from datetime import datetime
from ebay_monitor.ebay_api import EbayAPI

class EbayMonitor:
    def __init__(self, api=None):
        self.queries = {}
        self.known_items = {}
        self.active = False
        self.lock = threading.Lock()
        self.api = api or EbayAPI()
        self.monitor_thread = None  # Initialize thread attribute
        self.query_processed = threading.Event()  # Add event flag
        self.load_data()
        
    def load_data(self):
        try:
            if os.path.exists('queries.json'):
                with open('queries.json', 'r') as f:
                    data = json.load(f)
                    self.queries = data.get('queries', {})
                    # Convert known_items lists back to sets
                    self.known_items = {k: set(v) for k, v in data.get('known_items', {}).items()}
                    self.active = data.get('active', False)
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            # Initialize fresh data on error
            self.queries = {}
            self.known_items = {}
            self.active = False
            
    def save_data(self):
        data = {
            'queries': self.queries,
            'known_items': {k: list(v) for k, v in self.known_items.items()},
            'active': self.active
        }
        print(f"Saving data: {data}")  # Debug
        with open('queries.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Saved monitoring data")
        
    def add_query(self, query_id, keywords, filters):
        with self.lock:
            self.queries[query_id] = {
                'keywords': keywords,
                'filters': filters,
                'created': datetime.now().isoformat(),
                'first_run': True
            }
            self.known_items[query_id] = set()
            self.save_data()
            
    def remove_query(self, query_id):
        with self.lock:
            self.queries.pop(query_id, None)
            self.known_items.pop(query_id, None)
            self.save_data()
            
    def update_query(self, query_id, **kwargs):
        with self.lock:
            if query_id in self.queries:
                self.queries[query_id].update(kwargs)
                self.save_data()
            
    def _monitor_loop(self):
        print("Monitoring thread started")  # Debug
        while True:
            if self.active:
                print("Active monitoring cycle")  # Debug
                with self.lock:
                    queries = list(self.queries.items())
                    
                for query_id, config in queries:
                    if not self.active:
                        break
                    self._check_query(query_id, config)
                    
                time.sleep(0.5)
            else:
                time.sleep(0.2)
                
    def _check_query(self, query_id, config):
        try:
            with self.lock:
                # Get fresh reference to the actual query data
                if query_id not in self.queries:
                    return
                current_query = self.queries[query_id]
            
            if current_query['first_run']:
                results = self.api.search(
                    current_query['keywords'],
                    current_query['filters']['marketplace'],
                    current_query['filters']
                )
                items = [item['itemId'] for item in results.get('itemSummaries', [])]
                
                with self.lock:
                    # Update the actual query in the dictionary
                    self.queries[query_id]['first_run'] = False
                    self.known_items[query_id].update(items)
                    self.save_data()
            
            self.query_processed.set()
        except Exception as e:
            print(f"Error checking query: {str(e)}")
            
    def _send_notifications(self, query_id, items):
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not token or not chat_id:
            print("Telegram credentials missing - skipping notifications")
            return
        
        query = self.queries[query_id]
        base_url = "https://www.ebay.com/itm/"
        
        for item_id in items:
            message = (
                f"🚨 New Item Alert!\n"
                f"Search: {query['keywords']}\n"
                f"Item: {base_url}{item_id}"
            )
            
            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                )
            except Exception as e:
                print(f"Failed to send Telegram notification: {str(e)}")
        
    def start(self):
        if not self.active:
            self.active = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("Monitoring thread started")  # Debug
        self.save_data()
        
    # Additional helper methods 