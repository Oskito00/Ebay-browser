from app import db
from app.models import Query, Item
from app.utils.notifications import NotificationManager
from app.utils.scraper import scrape_ebay
from flask import current_app


def check_query(query_id):
    try:
        query = Query.query.get(query_id)
        if not query:
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
            db.session.bulk_insert_mappings(
                Item,
                [{
                    'ebay_id': item['ebay_id'],
                    'title': item['title'],
                    'price': item['price'],
                    'currency': item['currency'],
                    'original_price': item.get('original_price'),
                    'original_currency': item.get('original_currency'),
                    'url': item['url'],
                    'image_url': item.get('image_url'),
                    'seller': item.get('seller'),
                    'seller_rating': item.get('seller_rating'),
                    'condition': item.get('condition'),
                    'location_country': item.get('location', {}).get('country'),
                    'query_id': query_id
                } for item in items]
            )
            db.session.commit()
            return

        # Subsequent runs
        existing_urls = {item.ebay_id for item in query.items}
        new_items = []
        
        items = scrape_ebay(
            keywords=query.keywords,
            filters={
                'min_price': query.min_price,
                'max_price': query.max_price,
                'item_location': query.item_location
            },
            marketplace=query.marketplace
        )
        for item in items:
            if item['ebay_id'] not in existing_urls:
                new_item = Item(
                    ebay_id=item['ebay_id'],
                    title=item['title'],
                    price=item['price'],
                    currency=item['currency'],
                    original_price=item.get('original_price'),
                    original_currency=item.get('original_currency'),
                    url=item.get('url'),
                    image_url=item.get('image_url'),
                    seller=item.get('seller'),
                    seller_rating=item.get('seller_rating'),
                    condition=item.get('condition'),
                    location_country=item.get('location', {}).get('country'),
                    query_id=query_id
                )
                db.session.add(new_item)
                new_items.append(item)
        
        db.session.commit()
        
        if new_items and query.user.telegram_connected:
            NotificationManager.send_item_notification(query.user, new_items)

        current_app.logger.info(
            f"Query {query_id}: Scraped {len(items)} items, "
            f"Found {len(new_items)} new items"
        )

        #TODO: Add dealing with ended items
        #TODO: Add dealing with aution items as well as buy it now items

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Query {query_id} failed: {str(e)}")
