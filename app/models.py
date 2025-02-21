from datetime import datetime
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import NUMERIC

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    telegram_chat_id = db.Column(db.String(50))
    telegram_connected = db.Column(db.Boolean, default=False)
    telegram_notifications_enabled = db.Column(db.Boolean, default=False)
    notification_preferences = db.Column(db.JSON, default={
        'price_changes': True,
        'new_items': True,
        'interval': 'immediate'
    })
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    queries = db.relationship('Query', backref='user', lazy='dynamic')

    def get_id(self):
        return str(self.id)
        
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Query(db.Model):
    __tablename__ = 'queries'
    
    id = db.Column(db.Integer, primary_key=True)
    keywords = db.Column(db.String(255), nullable=False)
    check_interval = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    min_price = db.Column(db.Numeric(10,2))
    max_price = db.Column(db.Numeric(10,2))
    required_keywords = db.Column(db.String(255))
    excluded_keywords = db.Column(db.String(255))
    condition = db.Column(db.String(50))
    buying_options = db.Column(db.String(50), default='FIXED_PRICE|AUCTION')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    filters = db.Column(db.JSON)  # {min_price, max_price, condition, etc}
    is_active = db.Column(db.Boolean, default=False)
    last_checked = db.Column(db.DateTime)
    limit = db.Column(db.Integer, default=200)
    total_items = db.Column(db.Integer)  # Track total found
    price_alert_threshold = db.Column(db.Float, default=5.0)  # Percentage threshold
    marketplace = db.Column(db.String(10), nullable=False, default='EBAY_GB')
    item_location = db.Column(db.String(10), nullable=False, default='GB')
    
    items = db.relationship('Item', backref='query', cascade='all, delete-orphan')
    
class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(db.Integer, db.ForeignKey('queries.id'), nullable=False)
    keywords = db.Column(db.String(255))
    ebay_id = db.Column(db.String(50), nullable=False)
    legacy_id = db.Column(db.String(50))
    title = db.Column(db.String(255))
    price = db.Column(db.Float)
    currency = db.Column(db.String(10), nullable=False, default='GBP')
    url = db.Column(db.String(512))
    image_url = db.Column(db.String(255))
    seller = db.Column(db.String(100))
    seller_rating = db.Column(db.String(20))
    condition = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime)
    location_country = db.Column(db.String(10)) 
    postal_code = db.Column(db.String(20))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    buying_options = db.Column(db.Text)

    # New auction fields
    auction_details = db.Column(db.Text)  # JSON: bid_count, current_bid etc
    categories = db.Column(db.Text)  # JSON: {'ids': [], 'names': []}
    marketplace = db.Column(db.String(20))  # e.g. 'EBAY_GB'
    images = db.Column(db.Text)  # JSON: {'main': url, 'thumbnails': []}
    
    # Add composite unique constraint
    __table_args__ = (
        db.UniqueConstraint('ebay_id', 'query_id', name='uq_ebay_id_query'),
    )

class LongTermItem(db.Model):
    __tablename__ = 'long_term_items'
    
    id = db.Column(db.Integer, primary_key=True)
    keywords = db.Column(db.String(255), index=True)
    ebay_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255))
    price = db.Column(db.Float)
    currency = db.Column(db.String(10))
    url = db.Column(db.String(512))
    image_url = db.Column(db.String(255))
    seller = db.Column(db.String(100))
    seller_rating = db.Column(db.String(20))
    condition = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime)
    location_country = db.Column(db.String(10)) 
    postal_code = db.Column(db.String(20))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    buying_options = db.Column(db.Text)
    auction_details = db.Column(db.Text)  # JSON: bid_count, current_bid etc
    categories = db.Column(db.Text)  # JSON: {'ids': [], 'names': []}
    marketplace = db.Column(db.String(20))  # e.g. 'EBAY_GB'
    images = db.Column(db.Text)  # JSON: {'main': url, 'thumbnails': []}
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicates
    __table_args__ = (
        db.UniqueConstraint('ebay_id', 'recorded_at', name='uq_ebay_id_recorded'),
    )