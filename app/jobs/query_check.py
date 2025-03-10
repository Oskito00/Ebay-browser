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
    app = current_app._get_current_object()
    app.logger.debug(f"[Process Items] Starting processing for query {query.id}")
    app.logger.debug(f"[Process Items] Received {len(items)} items from scrape")

    new_items = []
    updated_items = []
    price_drops = []
    ending_auctions = []
    item_columns = {c.key for c in inspect(Item).mapper.column_attrs}

    new_items_count = 0
    existing_items_count = 0
    price_change_count = 0

    for idx, item_data in enumerate(items):
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

        if existing:
            existing_items_count += 1
            app.logger.debug(f"[Process Items] Item {idx+1}/{len(items)}: Existing item found (ID: {existing.id})")
        else:
            new_items_count += 1
            app.logger.debug(f"[Process Items] Item {idx+1}/{len(items)}: New item detected (eBay ID: {item_data['ebay_id']})")

        # Track price changes
        old_price = existing.price if existing else None
        new_price = item_data.get('price')

        if existing:
            # Update existing item
            update_count = 0
            for key in item_columns - {'id', 'query_id'}:
                if key in item_data and getattr(existing, key) != item_data[key]:
                    update_count += 1
                    setattr(existing, key, item_data[key])
            if update_count > 0:
                app.logger.debug(f"[Process Items] Updated {update_count} fields for item {existing.id}")
            updated_items.append(existing)
        else:
            # Create new item
            valid_data = {k: v for k, v in item_data.items() if k in item_columns}
            new_item = Item(**valid_data)
            db.session.add(new_item)
            new_items.append(new_item)

        # Price drop check
        if full_scan and existing and old_price is not None:
            if new_price < old_price and (query.max_price is None or new_price <= query.max_price):
                price_change_count += 1
                app.logger.debug(f"[Process Items] Price drop detected: {old_price} -> {new_price} (Item {existing.id})")

        # Auction ending detection
        end_time = item_data.get('end_time')
        print("DEBUG - [Process Items]: end_time", end_time)
        print("DEBUG - [Process Items]: datetime.now(timezone.utc)", datetime.now(timezone.utc))
        if end_time:    
            end_time = end_time.replace(tzinfo=timezone.utc)
            if end_time and (end_time - datetime.now(timezone.utc)) < timedelta(hours=12):
                ending_auctions.append(existing)
            app.logger.debug(f"[Process Items] Auction ending soon: {end_time} (Item {existing.id if existing else 'new'})")

    try:
        app.logger.debug(f"[Process Items] Committing changes to database")
        app.logger.debug(f"[Process Items] New items: {new_items_count}, Updated items: {len(updated_items)}")
        
        db.session.commit()
        
        app.logger.debug(f"[Process Items] Commit successful")
        app.logger.debug(f"[Process Items] Total price drops detected: {price_change_count}")
        app.logger.debug(f"[Process Items] Auctions ending soon: {len(ending_auctions)}")

        user = query.user
        prefs = user.notification_preferences

        if notify:
            app.logger.debug(f"[Process Items] Sending notifications (prefs: {prefs})")
            
            notification_counts = {
                'new_items': 0,
                'price_drops': 0,
                'auction_alerts': 0
            }

            if new_items and prefs.get('new_items', True):
                notification_counts['new_items'] = len(new_items)
                print("DEBUG Process Items: Sending new item notification")
                NotificationManager.send_item_notification(user, new_items)
            
            if price_drops and prefs.get('price_drops', True):
                notification_counts['price_drops'] = len(price_drops)
                print("DEBUG Process Items: Sending price drop notification")
                NotificationManager.send_price_drops(user, price_drops)
            
            if ending_auctions and prefs.get('auction_alerts', True):
                notification_counts['auction_alerts'] = len(ending_auctions)
                print("DEBUG Process Items: Sending auction alert notification")
                NotificationManager.send_auction_alerts(user, ending_auctions)

            app.logger.debug(f"[Process Items] Notifications sent: {notification_counts}")

        return new_items, updated_items

    except Exception as e:
        app.logger.error(f"[Process Items] Database commit failed: {str(e)}")
        db.session.rollback()
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