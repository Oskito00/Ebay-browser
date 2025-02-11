from unittest.mock import patch  # Correct import
from app.jobs.query_jobs import check_query
from app.models import Item, Query, User



def test_check_query_initial_run(session):  # Use session fixture
    # Create user
    user = User(email='test@example.com', password_hash='dummy')
    session.add(user)
    session.commit()  # Explicit commit
    
    # Create query
    query = Query(
        keywords="test",
        check_interval=5,
        user_id=user.id
    )
    session.add(query)
    session.commit()  # Explicit commit
    
    # Test logic
    with patch('app.utils.scraper.EbayAPI') as mock_api:
        mock_api.return_value.search.return_value = [{
            'ebay_id': '123',
            'title': 'Test Item',
            'price': 29.99,
            'currency': 'USD',
            'url': 'http://test.item'
        }]
        
        check_query(query.id)
    
    # Assertions
    assert session.query(Item).count() == 1