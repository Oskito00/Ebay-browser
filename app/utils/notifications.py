import requests
from flask import current_app, url_for
from datetime import datetime, timezone

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
    def send_item_notification(user, items, query=None):
        # Check preferences and connection
        if (not user.telegram_connected or 
            not user.notification_preferences.get('new_items', True) or
            not items):
            return False
        
        try:
            notifier = TelegramNotifier(
                current_app.config['TELEGRAM_BOT_TOKEN'],
                user.telegram_chat_id
            )
            
            # Improved message formatting
            query_text = f" for '{query.keywords}'" if query else ""
            message = (
                f"🎉 <b>New Items Found{query_text}!</b>\n\n"
                f"📥 Total new items: {len(items)}\n\n"
            )
            
            # Add top 3 items
            for item in items[:3]:
                message += (
                    f"🏷️ <a href='{item.url}'>{item.title}</a>\n"
                    f"💰 Price: {item.price} {item.currency}\n"
                    f"📍 Location: {item.location_country or 'N/A'}\n\n"
                )
            
            # Add view more link
            if query:
                message += f"🔍 <a href='{current_app.config['APP_URL']}/query/{query.id}'>View all items</a>"
            
            return notifier.send_message(message)
        
        except Exception as e:
            current_app.logger.error(f"Notification failed: {str(e)}")
            return False
    
    @staticmethod
    def send_test_notification(user, is_successfull_connection = False):
        try:
            chat_ids = [user.telegram_chat_ids['main']] + user.telegram_chat_ids['additional']
            for chat_id in chat_ids:
                notifier = TelegramNotifier(
                    current_app.config['TELEGRAM_BOT_TOKEN'],
                    chat_id
                )
                if is_successfull_connection:
                    notifier.send_message("✅ Your account has been successfully connected!")
                else:
                    print(f"Sending test notification to {chat_id}")
                    notifier.send_message("TESTING TESTING 123...")
        except Exception as e:
            print(f"Error sending test notification: {str(e)}")
            return False        
    
    
    @staticmethod
    def send_price_drops(user, drops):
        notifier = TelegramNotifier(
            current_app.config['TELEGRAM_BOT_TOKEN'],
            user.telegram_chat_id
        )
        for drop in drops:
            message = (
                "🛎️ **Price Alert**\n"
                f"📦 Item: {drop['item'].title}\n"
                f"💰 Price dropped from £{drop['old_price']} → £{drop['new_price']}\n"
                f"🔗 [View Item]({drop['item'].url})"
            )
            if user.notification_preferences.get('price_drops', True):
                notifier.send_message(message, parse_mode='Markdown')
                
    
    @staticmethod
    def send_auction_alerts(user, items):
        notifier = TelegramNotifier(
            current_app.config['TELEGRAM_BOT_TOKEN'],
            user.telegram_chat_id
        )
        for item in items:
            time_left = item.end_time - datetime.now(timezone.utc)
            hours_left = round(time_left.total_seconds() / 3600, 1)
            message = (
                "⏳ **Auction Ending Soon**\n"
                f"📦 Item: {item.title}\n"
                f"💰 Current Price: £{item.price}\n"
                f"⏰ Ends in: {hours_left} hours\n"
                f"🔗 [View Item]({item.url})"
            )
            if user.notification_preferences.get('auction_alerts', True):
                notifier.send_message(message, parse_mode='Markdown')
    
    
    

