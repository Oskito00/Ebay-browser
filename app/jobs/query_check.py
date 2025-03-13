from datetime import datetime, timezone, timedelta
from app import db, scheduler
from app.models import Item, Keyword, KeywordItems, User, UserQuery, UserQueryItems
from app.utils.levenshtein_string_similarity_helper import calculate_relevance_score
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
        session = db.session()
        try:
            with session.begin():
                # Get and check query
                query = UserQuery.query.get(query_id)
                
                if not query or not query.is_active:
                    app.logger.debug(f"[Job {query_id}] Aborting - no active query")
                    return
            # Get the kewords based on the query keyword_id
            keywords = Keyword.query.get(query.keyword_id)
            # Call scrape ebay with the right filters
            items = scrape_ebay(
                keywords.keyword_text,
                filters={'min_price': query.min_price, 'max_price': query.max_price, 'item_location': query.item_location,'condition': query.condition},
                required_keywords=query.required_keywords,
                excluded_keywords=query.excluded_keywords,
                marketplace=query.marketplace
            )
            app.logger.debug(f"[Job {query_id}] Found {len(items)} items")
            if query.first_run == True:
                process_items(items, query, full_scan=True, notify=False, first_run=True)
                query.first_run = False
            else:
                #It is not the first time the query has been run
                process_items(items, query, full_scan=True, notify=True, first_run=False)
                        
            query.last_full_run = datetime.now(timezone.utc)
            query.next_full_run = datetime.now(timezone.utc) + timedelta(hours=24)
            db.session.commit()
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
                query = UserQuery.query.get(query_id)
                if not query or not query.is_active:
                    return
            try:
                keywords = Keyword.query.get(query.keyword_id)
                new_items = scrape_new_items(
                    keywords.keyword_text,
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

def process_items(items, query, check_existing=False, full_scan=False, notify=True, first_run=False):
    app = current_app._get_current_object()
    app.logger.debug(f"[Process Items] Starting processing for query {query.query_id}")
    app.logger.debug(f"[Process Items] Received {len(items)} items from scrape")

    new_items = []
    updated_items = []
    price_drops = []
    ending_auctions = []
    item_columns = {c.key for c in inspect(Item).mapper.column_attrs}

    if first_run:
        relevance_scores = []

    # Get the keyword once at the start
    keyword = query.keyword
    current_time = datetime.now(timezone.utc)

    for idx, item_data in enumerate(items):
        # Remove query-specific data from item
        item_data.pop('query_id', None)
        item_data.pop('keywords', None)

        if first_run:
            relevance_score = calculate_relevance_score(query.keyword.keyword_text, item_data['title'])
            relevance_scores.append(relevance_score)

            # Find existing item globally (not per-query)
            existing = Item.query.filter_by(ebay_id=item_data['ebay_id']).first()
            if existing:
                app.logger.debug(f"[Process Items] Item {idx+1}/{len(items)}: Existing item found (ID: {existing.item_id})")
                # Check if item needs to be linked to keyword
                if not KeywordItems.query.filter_by(keyword_id=keyword.keyword_id, item_id=existing.item_id).first():
                    app.logger.debug(f"[Process Items] Linking existing item {existing.item_id} to keyword {keyword.keyword_text}")
                    db.session.add(KeywordItems(keyword_id=keyword.keyword_id, item_id=existing.item_id))
                # Check if the item is already linked to the query
                if not UserQueryItems.query.filter_by(query_id=query.query_id, item_id=existing.item_id).first():
                    app.logger.debug(f"[Process Items] Linking existing item {existing.item_id} to query {query.query_id}")
                    # If not add the link and include in new_items for notification
                    db.session.add(UserQueryItems(query_id=query.query_id, item_id=existing.item_id))
                    new_items.append(existing)
            else:
                # If we have never seen this item before, create a new global item
                valid_data = {k: v for k, v in item_data.items() if k in item_columns}
                new_item = Item(**valid_data)
                db.session.add(new_item)
                new_items.append(new_item)
                app.logger.debug(f"[Process Items] Item {idx+1}/{len(items)}: New item created (eBay ID: {item_data['ebay_id']})")

                # Flush to get the new item ID
                db.session.flush()
            
                # Link to keyword
                db.session.add(KeywordItems(
                keyword_id=keyword.keyword_id,
                item_id=new_item.item_id,
                found_at=current_time
                ))

                # Link to user query
                db.session.add(UserQueryItems(
                query_id=query.query_id,
                item_id=new_item.item_id,
                auction_ending_notification_sent=False
                ))
            
                db.session.commit()
        
        else:
            # Calculate the relevance score for the new item
            relevance_score = calculate_relevance_score(query.keyword.keyword_text, item_data['title'])
            # Find existing item globally (not per-query)
            existing = Item.query.filter_by(ebay_id=item_data['ebay_id']).first()
            if existing:
                app.logger.debug(f"[Process Items] Item {idx+1}/{len(items)}: Existing item found (ID: {existing.item_id})")
                # Check if item needs to be linked to keyword
                if not KeywordItems.query.filter_by(keyword_id=keyword.keyword_id, item_id=existing.item_id).first() and relevance_score > query.average_relevance_score - 0.15:
                    app.logger.debug(f"[Process Items] Linking existing item {existing.item_id} to keyword {keyword.keyword_text}")
                    db.session.add(KeywordItems(keyword_id=keyword.keyword_id, item_id=existing.item_id))
                # Check if the item is already linked to the query
                if not UserQueryItems.query.filter_by(query_id=query.query_id, item_id=existing.item_id).first() and relevance_score > query.average_relevance_score - 0.15:
                    app.logger.debug(f"[Process Items] Linking existing item {existing.item_id} to query {query.query_id}")
                    # If not add the link and include in new_items for notification
                    db.session.add(UserQueryItems(query_id=query.query_id, item_id=existing.item_id))
                    new_items.append(existing)
            else:
                # If we have never seen this item before, create a new global item
                valid_data = {k: v for k, v in item_data.items() if k in item_columns}
                new_item = Item(**valid_data)
                db.session.add(new_item)
                new_items.append(new_item)
                app.logger.debug(f"[Process Items] Item {idx+1}/{len(items)}: New item created (eBay ID: {item_data['ebay_id']})")

                # Flush to get the new item ID
                db.session.flush()
            
                # Link to keyword
                if relevance_score > query.average_relevance_score - 0.15:  
                    db.session.add(KeywordItems(
                    keyword_id=keyword.keyword_id,
                    item_id=new_item.item_id,
                    found_at=current_time
                    ))

                # Link to user query
                if relevance_score > query.average_relevance_score - 0.15:
                    db.session.add(UserQueryItems(
                    query_id=query.query_id,
                    item_id=new_item.item_id,
                    auction_ending_notification_sent=False
                    ))
            
                db.session.commit()
        

        # Update existing item if needed
        print(existing)
        if existing:
            update_count = 0
            for key in item_columns - {'item_id', 'created_at'}:
                if key in item_data and getattr(existing, key) != item_data[key]:
                    update_count += 1
                    setattr(existing, key, item_data[key])
                    existing.last_updated = current_time
            if update_count > 0:
                updated_items.append(existing)
                app.logger.debug(f"[Process Items] Updated {update_count} fields for item {existing.item_id}")

        # Track price changes (using first query that found the item)
        if full_scan and existing:
            old_price = existing.price
            new_price = item_data.get('price')
            if new_price and old_price and new_price < old_price:
                price_drops.append({
                    'item': existing,
                    'old_price': old_price,
                    'new_price': new_price
                })

        # Auction ending detection (now global)
        end_time = item_data.get('end_time')
        if end_time:
            end_time = end_time.replace(tzinfo=timezone.utc)
            if (end_time - current_time) < timedelta(hours=12):
                item = existing or new_item
                user_query_item = UserQueryItems.query.filter_by(
                    query_id=query.query_id,
                    item_id=item.item_id
                ).first()
                
                if user_query_item and not user_query_item.auction_ending_notification_sent:
                    ending_auctions.append(item)
                    user_query_item.auction_ending_notification_sent = True
    
    #Updates the average relevance score for the query (only on the first run)
    if first_run:
        UserQuery.query.filter_by(query_id=query.query_id).update({
            'average_relevance_score': sum(relevance_scores) / len(relevance_scores)
        })
    app.logger.debug(f"[Process Items] Updated relevance average score for query {query.query_id} to {query.average_relevance_score}")
                

    try:
        db.session.commit()
        app.logger.debug(f"[Process Items] Commit successful")
        app.logger.debug(f"[Process Items] New items: {len(new_items)}, Updated items: {len(updated_items)}")
        app.logger.debug(f"[Process Items] Price drops: {len(price_drops)}, Ending auctions: {len(ending_auctions)}")

        if notify:
            # Notify only for this query's user
            user = User.query.get(query.user_id)
            prefs = user.notification_preferences
            notification_counts = {'new_items': 0, 'price_drops': 0, 'auction_alerts': 0}
            
            if new_items:
                if new_items and prefs.get('new_items', True):
                    notification_counts['new_items'] = len(new_items)
                    NotificationManager.send_item_notification(user, new_items, query.keyword.keyword_text)

            if price_drops:
                if price_drops and prefs.get('price_drops', True):
                    notification_counts['price_drops'] = len(price_drops)
                    NotificationManager.send_price_drops(user, price_drops, query.keyword.keyword_text)

            if ending_auctions:
                if ending_auctions and prefs.get('auction_alerts', True):
                    notification_counts['auction_alerts'] = len(ending_auctions)
                    NotificationManager.send_auction_alerts(user, ending_auctions, query.keyword.keyword_text)

            app.logger.debug(f"[Process Items] Notifications sent: {notification_counts}")

        return new_items, updated_items

    except Exception as e:
        app.logger.error(f"[Process Items] Database commit failed: {str(e)}")
        db.session.rollback()
        raise


# Check queries job

def check_queries():
    app = scheduler.flask_app
    with app.app_context():
        # Get active query UUIDs
        active = {str(q.query_id) for q in UserQuery.query.filter_by(is_active=True).all()}
        
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


# ***********************
# HELPER FUNCTIONS
# ***********************