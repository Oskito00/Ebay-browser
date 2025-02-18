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
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        
    def send_message(self, message):
        """Send formatted message through Telegram"""
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                }
            )
            return response.status_code == 200
        except Exception as e:
            current_app.logger.error(f"Telegram send failed: {str(e)}")
            return False

class NotificationManager:
    @staticmethod
    def send_item_notification(user, items):
        if not user.telegram_connected or not items:
            return False
            
        notifier = TelegramNotifier(
            current_app.config['TELEGRAM_BOT_TOKEN'],
            user.telegram_chat_id
        )
        
        # Format message
        message = "<b>New Items Found!</b>\n\n"
        for item in items[:10]:  # Limit to 10 items per message
            # Use original price/currency if GBP, else use converted price/currency
            price_display = (
                f"{item.original_price} {item.original_currency}"
                if item.original_currency == 'GBP'
                else f"{item.price} {item.currency}"
            )
            
            message += (
                f"🏷️ <a href='{item.url}'>{item.title}</a>\n"
                f"💰 {price_display}\n"
                f"📍 {item.location_country or 'N/A'}\n\n"
            )
        
        if len(items) > 10:
            message += f"➕ {len(items)-10} more items found"
            
        return notifier.send_message(message)
    
    @staticmethod
    def send_test_notification(user):
        try:
            notifier = TelegramNotifier(
                current_app.config['TELEGRAM_BOT_TOKEN'],
                user.telegram_chat_id
            )
            print("Trying to send test notification")
            return notifier.send_message("Test notification sent")
        except Exception as e:
            print(f"Error sending test notification: {str(e)}")
            return False
    
    @staticmethod
    def send_price_alert(user, item, old_price):
        if not NotificationHandler.should_notify(user, 'price_changes'):
            return False
            
        notifier = TelegramNotifier(
            current_app.config['TELEGRAM_BOT_TOKEN'],
            user.telegram_chat_id
        )
        
        message = NotificationManager.format_price_alert(user, item, old_price, item.price)
        
        return notifier.send_message(message)

    @staticmethod
    def format_price_alert(user, item, old_price, new_price):
        change_type = "dropped" if new_price < old_price else "increased"
        percent = abs((new_price - old_price) / old_price) * 100
        
        return f"""
        💰 Price {change_type} by {percent:.1f}% for {item.title}
        🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}
        💰 From {old_price} {item.currency} to {new_price} {item.currency}
        🔗 {item.url}
        📊 <a href="{url_for('item_detail', item_id=item.id, _external=True)}">Price History</a>
        """.strip()
    

