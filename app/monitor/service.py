from decimal import Decimal
import logging
from datetime import datetime, timedelta

from flask import request
from app import db
from app.ebay.api import EbayAPI
from app.models import Query, Item
from app.utils.notifications import NotificationManager


logger = logging.getLogger(__name__)

class MonitoringService:
    def __init__(self):
        marketplace = request.form.get('marketplace', 'EBAY_GB')
        self.ebay_api = EbayAPI(marketplace=marketplace)
        self.check_interval = timedelta(minutes=request.form.get('check_interval', 5))
    
    def run_checks(self):
        """Main entry point for monitoring checks"""
        try:
            queries = self.get_queries_due_for_check()
            for query in queries:
                self.process_query(query)
        except Exception as e:
            logger.error(f"Monitoring failed: {str(e)}")
    
    def get_queries_due_for_check(self):
        """Retrieve active queries needing a check"""
        return Query.query.filter(
            Query.is_active == True,
            (Query.last_checked == None) | 
            (Query.last_checked < datetime.utcnow() - self.check_interval)
        ).all()
    
    def process_query(self, query):
        """Process a single query"""
        logger.info(f"Processing query {query.id}: {query.keywords}")
        
        # Fetch current items from eBay
        current_items = self.fetch_current_items(query)
        current_ids = {item['ebay_id'] for item in current_items}
        
        # Identify new items
        new_items = [item for item in current_items 
                    if not self.item_exists(query.id, item['ebay_id'])]
        
        # Save and notify
        if new_items:
            self.save_new_items(query, new_items)
            self.send_notifications(query, new_items)
        
        # Update query status
        query.last_checked = datetime.utcnow()
        db.session.commit()
    
    def fetch_current_items(self, query):
        """Fetch all items for query from eBay API"""
        api = EbayAPI(marketplace=query.marketplace)
        return api.search_all_pages(
            keywords=query.keywords,
            filters=query.filters
        )
    
    def item_exists(self, query_id, ebay_id):
        """Check if item already exists in database"""
        return db.session.query(
            Item.query.filter_by(query_id=query_id, ebay_id=ebay_id).exists()
        ).scalar()
    
    def save_new_items(self, query, items):
        """Persist new items to database"""
        for item_data in items:
            item = Item(
                ebay_id=item_data['ebay_id'],
                title=item_data['title'],
                price=item_data['price'],
                currency=item_data['currency'],
                url=item_data['url'],
                query_id=query.id,
                first_seen=datetime.utcnow()
            )
            db.session.add(item)
        db.session.commit()
    
    def send_notifications(self, query, new_items):
        """Trigger notifications for new items"""
        NotificationManager.send(
            user=query.user,
            query=query,
            new_items=new_items
        )

    def process_results(self, query, items):
        current_ids = {i['itemId'] for i in items}
        
        # Deactivate missing items
        Item.query.filter_by(query_id=query.id)\
                 .filter(Item.ebay_item_id.not_in(current_ids))\
                 .update({'is_active': False})
        
        # Process current items
        for item_data in items:
            self.process_item(query, item_data)
        
        db.session.commit()

    def process_item(self, query, item_data):
        item = Item.query.filter_by(ebay_item_id=item_data['itemId']).first()
        
        if item:
            self.handle_existing_item(item, item_data)
        else:
            self.handle_new_item(query, item_data)

    def handle_existing_item(self, item, item_data):
        new_price = Decimal(item_data['price']['value'])
        if item.price != new_price:
            self.handle_price_change(item, new_price)
        item.is_active = True
        item.last_seen = datetime.utcnow()

    def handle_price_change(self, item, new_price):
        old_price = item.price
        percent_change = abs((new_price - old_price) / old_price) * 100
        
        if percent_change >= item.query.price_alert_threshold:
            self.send_price_alert(item, old_price, new_price)
        
        item.price = new_price
        item.price_history.append({
            'old_price': float(old_price),
            'new_price': float(new_price),
            'timestamp': datetime.utcnow().isoformat()
        })

    def send_price_alert(self, item, old_price, new_price):
        NotificationManager.send_price_alert(
            user=item.query.user,
            item=item,
            old_price=old_price,
            new_price=new_price
        )

    def handle_new_item(self, query, item_data):
        new_item = Item(
            ebay_item_id=item_data['itemId'],
            title=item_data['title'],
            price=Decimal(item_data['price']['value']),
            currency=item_data['price']['currency'],
            query_id=query.id,
            url=self.generate_ebay_url(item_data['itemId'])
        )
        db.session.add(new_item)
        NotificationManager.send_item_notification(
            user=query.user,
            items=[new_item]
        )

    @staticmethod
    def generate_ebay_url(item_id):
        base_id = item_id.split('|')[-1]
        return f"https://www.ebay.com/itm/{base_id}" 