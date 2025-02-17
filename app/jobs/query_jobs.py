import time
from app import db
from app.models import Query, Item
from app.utils.notifications import NotificationManager
from app.utils.scraper import scrape_ebay, scrape_new_items
from flask import current_app
from sqlalchemy import select
from app import create_app
from apscheduler.jobstores.base import ConflictingIdError


def check_query(query_id):
    app = create_app()
    
    with app.app_context():
        try:
            from app.models import Query
            app.logger.debug(f"Checking query {query_id}")
            app.logger.debug(f"START check_query {query_id}")
            query = Query.query.get(query_id)
            app.logger.debug(f"Checking query: {query.keywords}")
            if not query:
                app.logger.error(f"Query {query_id} not found")
                return
            
            # First run logic
            if not query.items:
                items = scrape_ebay(
                    keywords=query.keywords,
                    filters={
                        'min_price': query.min_price,
                        'max_price': query.max_price,
                        'item_location': query.item_location
                    },
                    marketplace=query.marketplace
                )
                
                # Batch insert
                new_items = []
                for item in items:
                    new_item = Item(
                        ebay_id=item['ebay_id'],
                        title=item['title'],
                        price=item['price'],
                        currency=item.get('currency', 'USD'),
                        original_price=item.get('original_price'),
                        original_currency=item.get('original_currency'),
                        url=item['url'],
                        image_url=item.get('image_url'),
                        seller=item.get('seller'),
                        seller_rating=item.get('seller_rating'),
                        condition=item.get('condition'),
                        location_country=item.get('location', {}).get('country'),
                        query_id=query_id
                    )
                    new_items.append(new_item)
                db.session.add_all(new_items)
                db.session.commit()
                return

            # Subsequent runs
            existing_urls = {item.ebay_id for item in query.items}
            new_items = []
            
            items = scrape_new_items(
                keywords=query.keywords,
                filters={
                    'min_price': query.min_price,
                    'max_price': query.max_price,
                    'item_location': query.item_location
                },
                marketplace=query.marketplace
            )
            for item in items:
                if item['ebay_id'] in existing_urls:
                    print(f"Item {item['ebay_id']} already exists")
                    continue
                if item['ebay_id'] not in existing_urls:
                    try:
                        new_item = Item(
                            ebay_id=item['ebay_id'],
                            title=item['title'],
                            price=item['price'],
                            currency=item.get('currency', 'USD'),
                            original_price=item.get('original_price'),
                            original_currency=item.get('original_currency'),
                            url=item['url'],
                            image_url=item.get('image_url'),
                            seller=item.get('seller'),
                            seller_rating=item.get('seller_rating'),
                            condition=item.get('condition'),
                            location_country=item.get('location', {}).get('country'),
                            query_id=query_id
                        )
                        db.session.add(new_item)
                        new_items.append(new_item)
                    except KeyError as e:
                        app.logger.error(f"Missing field {e} in item: {item}")
                        continue
            
            if new_items:
                db.session.add_all(new_items)
                db.session.commit()  # Explicit commit
                
                if query.user.telegram_connected:
                    NotificationManager.send_item_notification(query.user, new_items)
                    
            app.logger.info(
                f"Query {query_id}: Scraped {len(items)} items, "
                f"Found {len(new_items)} new items"
            )
            app.logger.debug(f"Found {len(new_items)} new items")
            if new_items:
                db.session.add_all(new_items)
                db.session.commit()
                app.logger.debug("Items committed to database")

            #TODO: Add dealing with ended items
            #TODO: Add dealing with aution items as well as buy it now items
            #TODO: Add notifications for price changes
            #TODO: Deal tith items dissapearing from the search results
            time.sleep(2)

        except ConflictingIdError:
            app.logger.warning(f"Job query_{query_id} already running")
        except Exception as e:
            app.logger.error(f"Error: {str(e)}")
            db.session.rollback()
            raise
        finally:
            db.session.remove()
    app.logger.debug(f"END check_query {query_id}")
