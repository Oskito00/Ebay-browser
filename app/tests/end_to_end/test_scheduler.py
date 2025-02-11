from app.models import Item, Query, User
from app.jobs import query_jobs  # Add this import
from unittest.mock import patch


def test_debug_scraper_and_db(app, session):
    with app.app_context():
        # Setup
        user = User(email='debug@test.com')
        query = Query(
            keywords='debug test',
            check_interval=1,
            user=user
        )
        session.add_all([user, query])
        session.commit()

        # Mock scraper to return test data
        with patch('app.jobs.query_jobs.scrape_ebay') as mock_scrape:
            mock_scrape.return_value = [{
                'ebay_id': 'TEST123',
                'title': 'Test Debug Item',
                'price': 50.0,
                'currency': 'GBP',
                'url': 'http://test.item'
            }]

            # Run check_query
            from app.jobs.query_jobs import check_query
            check_query(query.id)
            
            # Verify scraper called with correct args
            mock_scrape.assert_called_once_with(
                keywords='debug test',
                filters={
                    'min_price': None,
                    'max_price': None,
                    'item_location': 'GB'
                },
                marketplace='EBAY_GB'
            )
        
        # Check saved items
        items = session.query(Item).filter_by(query_id=query.id).all()
        print("\n=== Saved Items ===")
        for item in items:
            print(f"ID: {item.ebay_id}, Title: {item.title}, Price: {item.price}")

        assert len(items) == 1
        assert items[0].ebay_id == 'TEST123'


def test_telegram_notification(app, session):
    with app.app_context():
        # Setup user with Telegram connected
        user = User(
            email='telegram@test.com',
            telegram_connected=True,
            telegram_chat_id='123456789'
        )
        query = Query(
            keywords='telegram test',
            check_interval=1,
            user=user
        )
        session.add_all([user, query])
        session.commit()

        # Mock scraper and Telegram
        with patch('app.jobs.query_jobs.scrape_ebay') as mock_scrape, \
             patch('app.utils.notifications.TelegramNotifier.send_message') as mock_send:

            mock_scrape.return_value = [{
                'ebay_id': 'TG123',
                'title': 'Telegram Test Item',
                'price': 75.0,
                'currency': 'GBP',
                'url': 'http://telegram.item',
                'location_country': 'UK'
            }]

            # Run query check
            from app.jobs.query_jobs import check_query
            check_query(query.id)
            
            # Verify notification sent
            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert "New Items Found!" in message
            assert "Telegram Test Item" in message
            assert "75.0 GBP" in message


def test_telegram_notification_flow(app, session):
    # Force testing config
    app.config['TELEGRAM_BOT_TOKEN'] = 'TEST_BOT_TOKEN'
    
    with app.app_context():
        # Setup user with Telegram
        user = User(
            email='telegram@test.com',
            telegram_connected=True,
            telegram_chat_id='TEST_CHAT_ID',
            notification_preferences={'new_items': True}
        )
        query = Query(
            keywords='telegram test',
            check_interval=1,
            user=user
        )
        session.add_all([user, query])
        session.commit()

        # Mock services
        with patch('app.jobs.query_jobs.scrape_ebay') as mock_scrape, \
             patch('app.utils.notifications.TelegramNotifier') as mock_telegram:

            # First run - save item (no notification)
            mock_scrape.return_value = [{
                'ebay_id': 'TG123',
                'title': 'First Item',
                'price': 100.0,
                'currency': 'GBP',
                'url': 'http://first.item'
            }]
            query_jobs.check_query(query.id)
            mock_telegram.return_value.send_message.assert_not_called()

            # Second run - same item (no notification)
            query_jobs.check_query(query.id)
            mock_telegram.return_value.send_message.assert_not_called()

            # Third run - new item (send notification)
            mock_scrape.return_value = [
                {
                    'ebay_id': 'TG123',
                    'title': 'First Item',
                    'price': 100.0,
                    'currency': 'GBP',
                    'url': 'http://first.item'
                },
                {
                    'ebay_id': 'TG456',
                    'title': 'New Item',
                    'price': 150.0,
                    'currency': 'GBP',
                    'url': 'http://new.item'
                }
            ]
            query_jobs.check_query(query.id)
            
            # Verify notification
            mock_telegram.return_value.send_message.assert_called_once()
            message = mock_telegram.return_value.send_message.call_args[0][0]
            assert "New Items Found!" in message
            assert "New Item" in message
            assert "150.0" in message