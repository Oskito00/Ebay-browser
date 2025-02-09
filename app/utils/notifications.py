import requests
from flask import current_app, url_for
from datetime import datetime

class NotificationHandler:
    @staticmethod
    def should_notify(user, notification_type):
        return (
            user.telegram_notifications_enabled and
            user.notification_preferences.get(notification_type, True)
        )

class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
    
    def send(self, message):
        try:
            response = requests.post(
                self.base_url,
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                },
                timeout=5
            )
            return response.ok
        except Exception as e:
            current_app.logger.error(f"Telegram send failed: {str(e)}")
            return False

class NotificationManager:
    @staticmethod
    def send_item_notification(user, items):
        if not NotificationHandler.should_notify(user, 'new_items'):
            return False
            
        notifier = TelegramNotifier(
            current_app.config['TELEGRAM_BOT_TOKEN'],
            user.telegram_chat_id
        )
        
        message = "<b>New eBay Items Found!</b>\n\n"
        for item in items:
            message += (
                f"🏷️ <a href='{item.url}'>{item.title}</a>\n"
                f"💰 Price: {item.price} {item.currency}\n\n"
            )
        
        return notifier.send(message)
    
    @staticmethod
    def send_price_alert(user, item, old_price):
        if not NotificationHandler.should_notify(user, 'price_changes'):
            return False
            
        notifier = TelegramNotifier(
            current_app.config['TELEGRAM_BOT_TOKEN'],
            user.telegram_chat_id
        )
        
        message = NotificationManager.format_price_alert(user, item, old_price, item.price)
        
        return notifier.send(message)

    @staticmethod
    def format_price_alert(user, item, old_price, new_price):
        change_type = "dropped" if new_price < old_price else "increased"
        percent = abs((new_price - old_price) / old_price) * 100
        
        return f"""
�� Price {change_type} by {percent:.1f}% for {item.title}
🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}
💰 From {old_price} {item.currency} to {new_price} {item.currency}
🔗 {item.url}
📊 <a href="{url_for('item_detail', item_id=item.id, _external=True)}">Price History</a>
        """.strip() 