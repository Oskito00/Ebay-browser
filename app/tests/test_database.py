from datetime import datetime, timezone
import time
from ..routes.queries import archive_items, load_historical_items
from ..models import User, Query, Item, LongTermItem
from ..extensions import db
from sqlalchemy.exc import IntegrityError
from unittest import mock


#**********************
#ARCHIVE ITEMS TESTS
#**********************

def test_archive_new_items(app):
    with app.app_context():
        user = User(email='test@example.com')
        query = Query(keywords='test', user=user, check_interval=5)
        item = Item(ebay_id='123', query=query)
        db.session.add_all([user, query, item])
        db.session.commit()
        
        archive_items(query)
        archived = LongTermItem.query.first()
        assert archived.ebay_id == '123'
        assert archived.keywords == 'test'


def test_archive_updates_existing(app):
    with app.app_context():
        user = User(email='test2@example.com')
        query = Query(keywords='test', user=user, check_interval=5)
        item = Item(
            ebay_id='123', 
            price=100.0, 
            query=query,
            keywords='test',  # Required
            marketplace='EBAY_UK'  # Required
        )
        db.session.add_all([user, query, item])
        db.session.commit()
        
        # First archive
        archive_items(query)
        archived = LongTermItem.query.first()
        original_id = archived.id
        
        # Update and re-archive
        item.price = 150.0
        db.session.commit()
        archive_items(query)
        
        # Verify update
        updated = LongTermItem.query.first()
        assert updated.price == 150.0
        assert updated.id == original_id  # Same record updated

def test_archive_null_price(app):
    with app.app_context():
        user = User(email='test3@example.com')
        query = Query(keywords='test', user=user, check_interval=5)
        item = Item(ebay_id='123', price=None, query=query)
        db.session.add_all([user, query, item])
        db.session.commit()
        
        archive_items(query)
        archived = LongTermItem.query.first()
        assert archived.price is None

def test_archive_unique_constraint(app):
    with app.app_context():
        user = User(email='test4@example.com')
        query1 = Query(keywords='test1', user=user, check_interval=5)
        query2 = Query(keywords='test2', user=user, check_interval=5)
        item1 = Item(ebay_id='123', query=query1, keywords='test1')
        item2 = Item(ebay_id='123', query=query2, keywords='test2')
        db.session.add_all([user, query1, query2, item1, item2])
        db.session.commit()
        
        print("\n=== Archiving Query1 ===")
        archive_items(query1)
        print("Archived Items:", [(a.ebay_id, a.keywords) for a in LongTermItem.query.all()])
        
        print("\n=== Archiving Query2 ===")
        archive_items(query2)
        print("Archived Items:", [(a.ebay_id, a.keywords) for a in LongTermItem.query.all()])
        
        print("\n=== Re-Archiving Query1 ===")
        archive_items(query1)
        print("Archived Items:", [(a.ebay_id, a.keywords) for a in LongTermItem.query.all()])
        
        archived = LongTermItem.query.all()
        print("Archived keywords:", [a.keywords for a in archived])
        
        assert len(archived) == 2, \
            f"Expected 2 items, got {len(archived)}"
        assert {a.keywords for a in archived} == {'test1', 'test2'}, \
            f"Keywords mismatch: {set(a.keywords for a in archived)}"

def test_archive_multiple_items(app):
    with app.app_context():
        user = User(email='test5@example.com')
        query = Query(keywords='test', user=user, check_interval=5)
        items = [
            Item(ebay_id=str(i), query=query)
            for i in range(5)
        ]
        db.session.add_all([user, query] + items)
        db.session.commit()
        
        archive_items(query)
        assert LongTermItem.query.count() == 5

#**********************
#LOAD HISTORICAL ITEMS TESTS
#**********************

def test_load_historical_basic(app):
    with app.app_context():
        # Create historical item
        hist = LongTermItem(
            keywords='test',
            ebay_id='123',
            title='Test Item',
            marketplace='EBAY_US',
            location_country='US',
            condition='NEW',
            price=100.0
        )
        db.session.add(hist)
        db.session.commit()
        
        # Create query with matching filters
        user = User(email='test@example.com')
        query = Query(
            keywords='test',
            user=user,
            marketplace='EBAY_US',
            item_location='US',
            condition='NEW',
            check_interval=5
        )
        db.session.add_all([user, query])
        db.session.commit()
        
        count = load_historical_items(query)
        assert count == 1

def test_load_historical_filters(app):
    with app.app_context():
        # Historical item with excluded keyword
        hist = LongTermItem(
            keywords='test',
            title='bad item',
            ebay_id='101',
        )
        db.session.add(hist)
        db.session.commit()

        hist = LongTermItem(
            keywords='test',
            title='good item',
            ebay_id='123',
        )
        db.session.add(hist)
        db.session.commit()
        
        query = Query(
            keywords='test',
            required_keywords='good',
            excluded_keywords='bad',
            check_interval=5
        )
        count = load_historical_items(query)
        assert count == 1  # Should be filtered out

def test_load_historical_duplicates(app):
    with app.app_context():
        # Existing item
        user = User(email='test@example.com')
        query = Query(keywords='test', user=user, check_interval=5)
        item = Item(ebay_id='123', query=query)
        db.session.add_all([user, query, item])
        
        # Historical item with same ebay_id
        hist = LongTermItem(
            keywords='test',
            ebay_id='123'
        )
        db.session.add(hist)
        db.session.commit()
        
        # Should not load duplicate
        count = load_historical_items(query)
        assert count == 0

def test_load_historical_multiple(app):
    with app.app_context():
        # Create user and associate with query
        user = User(email='test@example.com')
        db.session.add(user)
        db.session.commit()
        
        # Create query with user relationship
        query = Query(
            keywords='test',
            user_id=user.id,
            marketplace='EBAY_UK',
            item_location='GB',  # Maps to location_country
            condition='USED',
            check_interval=5
        )
        db.session.add(query)
        
        # Add historical items with matching fields
        for i in range(3):
            hist = LongTermItem(
                keywords='test',
                ebay_id=str(i),
                marketplace='EBAY_UK',
                location_country='GB',  # Match query.item_location='UK'
                condition='USED',
                price=50.0
            )
            db.session.add(hist)
        
        db.session.commit()
        
        # Test load
        count = load_historical_items(query)
        assert count == 3

def test_load_historical_performance(app):
    with app.app_context():
        # Create 1000 historical items
        user = User(email='perf@test.com')
        query = Query(keywords='perf_test', user=user, check_interval=5)
        
        with app.test_request_context():
            for i in range(1000):
                hist = LongTermItem(
                    keywords='perf_test',
                    ebay_id=str(i),
                    title=f'Item {i}',
                    price=i*10
                )
                db.session.add(hist)
            db.session.commit()
            
            start = time.time()
            count = load_historical_items(query)
            duration = time.time() - start
            
            assert count == 1000
            assert duration < 2.0  # Adjust based on your needs