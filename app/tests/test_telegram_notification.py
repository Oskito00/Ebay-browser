from app import create_app
from app.models import User, Item
from app.utils.notifications import NotificationManager

# Create app with proper config FIRST
app = create_app('default')
app.config['TELEGRAM_BOT_TOKEN'] = '7892050031:AAGJyt3kv7IygdrmRHD9IXCsRwi2CVIngqA'  # Put token here

with app.app_context():
    test_user = User.query.filter_by(email='oscar.alberigo@gmail.com').first()
    
    if not test_user or not test_user.telegram_connected:
        print("Error: User not configured")
        exit()

    # Test notification with real item data
    test_items = [
        Item(
            ebay_id='MANUAL123',
            title='Manual Test Item',
            price=99.99,
            currency='GBP',
            url='http://test.item',
            location_country='UK'
        )
    ]

    result = NotificationManager.send_item_notification(test_user, test_items)
    print("Success" if result else "Failed")