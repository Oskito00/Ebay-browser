from datetime import datetime, timezone, timedelta
import time
from app import db
from app.models import Query, Item
from app.utils.notifications import NotificationManager
from app.utils.scraper import scrape_ebay, scrape_new_items
from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.orm import Session


def full_scrape_job(query_id):
    with db.session() as session:
        query = session.get(Query, query_id)
        if not query or not query.is_active:
            return

        try:
            items = scrape_ebay(
                query.keywords,
                filters={'min_price': query.min_price, 'max_price': query.max_price, 'item_location': query.item_location,'condition': query.condition},
                required_keywords=query.required_keywords,
                excluded_keywords=query.excluded_keywords,
                marketplace=query.marketplace
            )
            process_items(items, query, full_scan=True)
            
            # Only update timestamps
            query.last_full_run = datetime.utcnow()
            query.next_full_run = datetime.utcnow() + timedelta(hours=24)
            session.commit()
            
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Full scrape failed: {e}")

def recent_scrape_job(query_id):
    with db.session() as session:
        query = session.get(Query, query_id)
        if not query or not query.is_active:
            return

        try:
            new_items = scrape_new_items(
                query.keywords,
                filters={'min_price': query.min_price, 'max_price': query.max_price, 'item_location': query.item_location,'condition': query.condition},
                required_keywords=query.required_keywords,
                excluded_keywords=query.excluded_keywords,
                marketplace=query.marketplace
            )
            process_items(new_items, query, check_existing=False)
            
        except Exception as e:
            current_app.logger.error(f"Recent scrape failed: {e}")

def process_items(items, query, check_existing=False, full_scan=False):
    new_items = []
    updated_items = []
    price_drops = []
    ending_auctions = []
    item_columns = {c.key for c in inspect(Item).mapper.column_attrs}

    for item_data in items:
        # Add query context
        item_data.update({
            'query_id': query.id,
            'keywords': query.keywords,
            'last_updated': datetime.utcnow()
        })
        
        # Find existing item
        existing = Item.query.filter(
            (Item.ebay_id == item_data['ebay_id']) &
            (Item.query_id == query.id)
        ).first()

        # Track price changes
        old_price = existing.price if existing else None
        new_price = item_data.get('price')

        if existing:
            # Update existing item
            for key in item_columns - {'id', 'query_id'}:
                if key in item_data:
                    setattr(existing, key, item_data[key])
            updated_items.append(existing)
        else:
            # Create new item
            valid_data = {k: v for k, v in item_data.items() if k in item_columns}
            new_item = Item(**valid_data)
            db.session.add(new_item)
            new_items.append(new_item)

        # Price drop check (only during full scans)
        if full_scan and existing and old_price is not None:
            if new_price < old_price and new_price <= query.max_price:
                price_drops.append({
                    'item': existing,
                    'old_price': old_price,
                    'new_price': new_price
                })

        # Auction ending detection
        end_time = item_data.get('end_time')
        if end_time and (end_time - datetime.utcnow()) < timedelta(hours=12):
            ending_auctions.append(existing)

    try:
        db.session.commit()
        user = query.user
        prefs = user.notification_preferences

        # Send notifications
        if new_items and prefs.get('new_items', True):
            NotificationManager.send_item_notification(user, new_items)
            
        if price_drops and prefs.get('price_drops', True):
            NotificationManager.send_price_drops(user, price_drops)
            
        if ending_auctions and prefs.get('auction_alerts', True):
            NotificationManager.send_auction_alerts(user, ending_auctions)

        return new_items, updated_items

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Item processing failed: {str(e)}")
        raise
