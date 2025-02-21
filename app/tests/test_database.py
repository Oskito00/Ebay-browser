from ..routes.queries import archive_items
from ..models import User, Query, Item, LongTermItem
from ..extensions import db


def test_archive_items(app):
    with app.app_context():
        # Create test data
        user = User(email='test@example.com')
        print("Trying to add user to users database")
        db.session.add(user)
        query = Query(
            keywords='test',
            user=user,
            check_interval=5
        )
        db.session.add(query)
        
        # Add test items
        item1 = Item(
            ebay_id='123',
            title='Test Item 1',
            price=10.0,
            query=query
        )
        item2 = Item(
            ebay_id='456',
            title='Test Item 2',
            price=20.0,
            query=query
        )
        db.session.add_all([item1, item2])
        db.session.commit()
        
        # Archive items
        archive_items(query)
        
        # Verify long-term storage
        archived = LongTermItem.query.all()
        assert len(archived) == 2
        assert {a.ebay_id for a in archived} == {'123', '456'}
        
        # Test update scenario
        item1.price = 15.0
        db.session.commit()
        archive_items(query)
        updated = LongTermItem.query.filter_by(ebay_id='123').first()
        assert updated.price == 15.0
