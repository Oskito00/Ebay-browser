from datetime import datetime, timezone
import uuid
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy import JSON, UUID, DateTime, String

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    telegram_chat_ids = db.Column(db.JSON, default={
        'main': None,
        'additional': []
    })
    telegram_connected = db.Column(db.Boolean, default=False)
    telegram_notifications_enabled = db.Column(db.Boolean, default=True)
    notification_preferences = db.Column(db.JSON, default={
        'price_drops': True,
        'new_items': True,
        'auction_alerts': True,
    })
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    query_usage = db.Column(db.Integer, default=0)

    # Stripe/Subscription
    stripe_customer_id = db.Column(db.String(50), index=True)
    stripe_subscription_id = db.Column(db.String(50), index=True)
    tier = db.Column(JSON, default={'name': 'free', 'query_limit': 0})
    subscription_status = db.Column(db.String(20), default='inactive')  # active/past_due/canceled/expired
    current_period_end = db.Column(db.DateTime)
    requested_change = db.Column(JSON)  # {'new_tier': 'pro', 'when': 'now|renewal'}
    pending_tier = db.Column(JSON)  # {'name': 'pro', 'query_limit': 100}
    pending_effective_date = db.Column(db.DateTime)
    cancellation_requested = db.Column(db.Boolean, default=False)
    last_checkout_session_id = db.Column(db.String(100))

    def get_id(self):
        return str(self.id)
        
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class Item(db.Model):
    __tablename__ = 'items'
    item_id = db.Column(db.Integer, primary_key=True)
    ebay_id = db.Column(db.String(50), unique=True, nullable=False)
    legacy_id = db.Column(db.String(50))
    title = db.Column(db.String(255))
    price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='GBP')
    url = db.Column(db.String(512))
    image_url = db.Column(db.String(255))
    seller = db.Column(db.String(100))
    seller_rating = db.Column(db.String(20))
    condition = db.Column(db.String(50))
    location_country = db.Column(db.String(10)) 
    postal_code = db.Column(db.String(20))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    buying_options = db.Column(db.Text)
    auction_details = db.Column(db.Text)
    categories = db.Column(db.Text)
    marketplace = db.Column(db.String(20))
    images = db.Column(db.Text)
    last_updated = db.Column(db.DateTime)
    
class UserQueryItems(db.Model):
    __tablename__ = 'user_query_items'
    query_id = db.Column(String(36), db.ForeignKey('user_queries.query_id'), primary_key=True, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.item_id'), primary_key=True, nullable=False)
    auction_ending_notification_sent = db.Column(db.Boolean, default=False)

class UserQuery(db.Model):
    __tablename__ = 'user_queries'
    # Core metadata

    query_id = db.Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keywords.keyword_id'), nullable=False)
    keyword = db.relationship('Keyword', backref='user_queries')
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)

    # Scheduling/operational
    check_interval = db.Column(db.Integer, default=5)  # Default: 5 minutes
    marketplace = db.Column(db.String(10), default='EBAY_GB')
    item_location = db.Column(db.String(10), default='GB')
    last_full_run = db.Column(db.DateTime)
    next_full_run = db.Column(db.DateTime)
    last_recent_run = db.Column(db.DateTime)

    # Critical filters (indexed)
    min_price = db.Column(db.Numeric(10, 2), index=True)
    max_price = db.Column(db.Numeric(10, 2), index=True)
    condition = db.Column(db.String(50), index=True)
    item_location = db.Column(db.String(50), index=True)
    required_keywords = db.Column(db.String(255), index=True)
    excluded_keywords = db.Column(db.String(255), index=True)
    buying_options = db.Column(db.String(255), index=True)
    first_run = db.Column(db.Boolean, default=True)

class Keyword(db.Model):
    __tablename__ = 'keywords'
    keyword_id = db.Column(db.Integer, primary_key=True)
    keyword_text = db.Column(db.String(255), nullable=False)

class KeywordItems(db.Model):
    __tablename__ = 'keyword_items'
    keyword_id = db.Column(db.Integer, db.ForeignKey('keywords.keyword_id'), primary_key=True, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.item_id'), primary_key=True, nullable=False)
    found_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

# Feedback data to train the ML model
class ItemRelevanceFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.item_id'), nullable=False)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keywords.keyword_id'), nullable=False)
    is_relevant = db.Column(db.Boolean, nullable=False)  # True/False for user feedback
    simple_hybrid_levenshtein_confidence = db.Column(db.Float)  # Optional: Hybrid confidence score
    cosine_similarity = db.Column(db.Float)  # Optional: Cosine similarity score
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feedback_type = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    cancellation_reasons = db.Column(db.String(255))  # Comma-separated reasons
    cancellation_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

#**********************
#HELPER FUNCTIONS
#**********************

def copy_item(source, target):
    """Copy fields between ItemBase subclasses, excluding id"""
    excluded_attrs = {'id', '_sa_instance_state'}
    for attr in vars(source).keys():
        if (
            not attr.startswith('_') 
            and attr not in excluded_attrs
            and hasattr(target, attr)
        ):
            setattr(target, attr, getattr(source, attr))