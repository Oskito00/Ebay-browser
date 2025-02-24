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
    print(f"[DEBUG] App context: {app}")  # Debug 1
    
    with app.app_context():
        try:
            session = db.session
            print(f"[DEBUG] Session type: {type(session)}")  # Debug 2
            
            with session.begin():
                print("[DEBUG] Inside transaction context")  # Debug 3
                query = session.query(Query).get(query_id)
                print(f"[DEBUG] Query retrieved: {query}")  # Debug 4
                
                if not query or not query.is_active:
                    print("[DEBUG] Query inactive or missing")  # Debug 5
                    return

                try:
                    print("[DEBUG] Starting scrape")  # Debug 6
                    items = scrape_ebay(
                        query.keywords,
                        filters={'min_price': query.min_price, 'max_price': query.max_price, 'item_location': query.item_location,'condition': query.condition},
                        required_keywords=query.required_keywords,
                        excluded_keywords=query.excluded_keywords,
                        marketplace=query.marketplace
                    )
                    process_items(items, query, full_scan=True)
                    
                    # Use timezone-aware datetimes
                    now = datetime.now(timezone.utc)
                    query.last_full_run = now
                    query.next_full_run = now + timedelta(hours=24)
                    print("[DEBUG] Updates applied")  # Debug 7
                    
                except Exception as e:
                    print(f"[DEBUG] Scrape error: {e}")  # Debug 8
                    session.rollback()
                    app.logger.error(f"Full scrape failed: {e}")
        except Exception as e:
            print(f"[DEBUG] Outer error: {e}")  # Debug 9
            app.logger.error(f"Error: {e}")

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
                process_items(new_items, query, check_existing=False)
                
            except Exception as e:
                app.logger.error(f"Recent scrape failed: {e}")
        except Exception as e:
            app.logger.error(f"Error: {e}")

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


def check_queries():
    app = scheduler.flask_app
    with app.app_context():
        print(Query.query.count())
        # Get active queries
        active = {q.id for q in Query.query.filter_by(is_active=True).all()}
        
        scheduled = set()
        for job in scheduler.get_jobs():
            if job.id.startswith('query_'):
                try:
                    q_id = int(job.id.split('_')[1])
                    scheduled.add(q_id)
                except (ValueError, IndexError):
                    pass
        
        # Add missing jobs
        for qid in active - scheduled:
            add_query_jobs(qid)  # Call helper function
            
        # Remove deleted jobs
        for qid in scheduled - active:
            remove_query_jobs(qid)  # Call helper function