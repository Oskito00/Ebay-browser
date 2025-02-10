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
        queries = self.get_active_queries()
        for query in queries:
            self.process_query(query)
    
    def get_active_queries(self):
        """Get queries needing check"""
        return Query.query.filter(
            Query.is_active == True,
            (Query.last_checked == None) | 
            (Query.last_checked < datetime.utcnow() - self.check_interval)
        ).all()
    
    def process_query(self, query):
        """Process query with pagination"""
        try:
            all_items = []
            offset = 0
            limit = query.limit or 200
            
            while True:
                results = self.ebay_api.search(
                    keywords=query.keywords,
                    filters=query.filters,
                    limit=limit,
                    offset=offset
                )
                
                all_items.extend(results.get('itemSummaries', []))
                
                # Check if we've got all items
                if not results.get('itemSummaries') or \
                   len(all_items) >= results.get('total', 0):
                    break
                    
                offset += limit
            
            self.process_results(query, all_items)
            query.last_checked = datetime.utcnow()
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Query {query.id} failed: {str(e)}")
            db.session.rollback()

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