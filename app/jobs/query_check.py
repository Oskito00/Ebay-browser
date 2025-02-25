from datetime import datetime, timezone, timedelta
import time
from app import db, scheduler
from app.models import Query, Item
from app.utils.notifications import NotificationManager
from app.utils.scraper import scrape_ebay, scrape_new_items
from flask import current_app
from sqlalchemy import inspect
from app.scheduler.core import scheduler  # Import the instance
from app.scheduler.job_manager import add_query_jobs, remove_query_jobs



def full_scrape_job(query_id):
    app = current_app._get_current_object() if current_app else scheduler.flask_app
    app.logger.debug(f"[Job {query_id}] Starting full scrape")
    
    with app.app_context():
        app.logger.debug(f"[Job {query_id}] App context entered")
        
        session = db.session()
        app.logger.debug(f"[Job {query_id}] Session created: {id(session)}")
        
        try:
            with session.begin():
                # Get and check query
                query = session.query(Query).get(query_id)
                app.logger.debug(f"[Job {query_id}] Query status: {'Active' if query and query.is_active else 'Inactive/Missing'}")
                
                if not query or not query.is_active:
                    app.logger.debug(f"[Job {query_id}] Aborting - no active query")
                    return

            # Scraping (outside transaction)
            app.logger.debug(f"[Job {query_id}] Scraping eBay...")
            items = scrape_ebay(
                query.keywords,
                filters={'min_price': query.min_price, 'max_price': query.max_price, 'item_location': query.item_location,'condition': query.condition},
                required_keywords=query.required_keywords,
                excluded_keywords=query.excluded_keywords,
                marketplace=query.marketplace
            )
            app.logger.debug(f"[Job {query_id}] Found {len(items)} items")
            if query.needs_scheduling == True:
                #It is the first time the query has been run
                process_items(items, query, full_scan=True, notify=False)
            else:
                #It is not the first time the query has been run
                process_items(items, query, full_scan=True, notify=True)
            app.logger.debug(f"[Job {query_id}] Processed {len(items)} items")

            # Update timestamps in same session
            
            app.logger.debug(f"[Job {query_id}] Updating query fields")
            
            query.last_full_run = datetime.now(timezone.utc)
            query.next_full_run = datetime.now(timezone.utc) + timedelta(hours=24)
            query.needs_scheduling = False
            db.session.commit()
            app.logger.debug(f"[Job {query_id}] Query fields updated")
        except Exception as e:
            app.logger.error(f"[Job {query_id}] Error: {str(e)}", exc_info=True)
        finally:
            session.close()
            db.session.remove()
            app.logger.debug(f"[Job {query_id}] Session closed and removed")

def recent_scrape_job(query_id):
    app = current_app._get_current_object() if current_app else scheduler.flask_app
    
    with app.app_context():
        try:
            session = db.session
            
            with session.begin():
                # Correct query method
                query = session.query(Query).get(query_id)
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
                process_items(new_items, query, check_existing=False, notify=True)

                query.last_recent_run = datetime.now(timezone.utc)
                db.session.commit()
                
            except Exception as e:
                app.logger.error(f"Recent scrape failed: {e}")
        except Exception as e:
            app.logger.error(f"Error: {e}")

def process_items(items, query, check_existing=False, full_scan=False, notify=True):
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
            'last_updated': datetime.now(timezone.utc)
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
            # Handle cases where query.max_price might be None
            if new_price < old_price and (query.max_price is None or new_price <= query.max_price):
                price_drops.append({
                    'item': existing,
                    'old_price': old_price,
                    'new_price': new_price
                })

        # Auction ending detection
        end_time = item_data.get('end_time')
        if end_time and (end_time - datetime.now(timezone.utc)) < timedelta(hours=12):
            ending_auctions.append(existing)

    try:
        db.session.commit()
        user = query.user
        prefs = user.notification_preferences

        if notify:
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


def check_queries():
    app = scheduler.flask_app
    with app.app_context():
        # Get active query UUIDs
        active = {str(q.id) for q in Query.query.filter_by(is_active=True).all()}
        
        # Get scheduled UUIDs from job IDs
        scheduled = set()
        for job in scheduler.get_jobs():
            if job.id.startswith('query_'):
                parts = job.id.split('_')
                if len(parts) >= 3:
                    uuid_str = '_'.join(parts[1:-1])  # Handle UUIDs with underscores
                    scheduled.add(uuid_str)
        
        # Add missing jobs
        for qid in active - scheduled:
            add_query_jobs(qid)
            
        # Remove deleted jobs
        for qid in scheduled - active:
            remove_query_jobs(qid)