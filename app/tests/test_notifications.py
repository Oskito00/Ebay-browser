
from datetime import datetime, timezone
from pytest import Item
from app.models import Query, User
from app.tests.conftest import db_session
from app.utils.notifications import NotificationManager


def test_new_item_notification():
    user = User(email='test@test.com')
    user.telegram_chat_ids = {'main': 1234567890}
    user.telegram_chat_ids['additional'] = [1234567891, 1234567892]
    user.notification_preferences = {'new_items': True, 'price_drops': True, 'auction_alerts': True}
    db_session.add(user)
    db_session.commit()

    query = Query(keywords='test', check_interval=10, user_id=user.id)
    db_session.add(query)
    db_session.commit()

    items = [Item(title='test', price=100, end_time=datetime.now(timezone.utc), query_id=query.id)]

    notfications_sent = NotificationManager.send_item_notification(user, items, query)

    assert notfications_sent == 3
