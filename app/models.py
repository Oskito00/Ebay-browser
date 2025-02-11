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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    filters = db.Column(db.JSON)  # {min_price, max_price, condition, etc}
    is_active = db.Column(db.Boolean, default=False)
    last_checked = db.Column(db.DateTime)
    limit = db.Column(db.Integer, default=200)
    total_items = db.Column(db.Integer)  # Track total found
    price_alert_threshold = db.Column(db.Float, default=5.0)  # Percentage threshold
    marketplace = db.Column(db.String(10), nullable=False, default='EBAY_GB')
    item_location = db.Column(db.String(10), nullable=False, default='GB')
    
    items = db.relationship('Item', backref='query', lazy=True)

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    ebay_id = db.Column(db.String(50), index=True, unique=True, nullable=False)
    query_id = db.Column(db.Integer, db.ForeignKey('queries.id'), index=True, nullable=False)
    title = db.Column(db.String(255))
    price = db.Column(db.Float)
    url = db.Column(db.String(512))
    image_url = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime) 
    currency = db.Column(db.String(10), nullable=False, default='GBP')
    legacy_id = db.Column(db.String(50))
    original_price = db.Column(db.Numeric(10,2))
    original_currency = db.Column(db.String(3))
    seller = db.Column(db.String(100))
    seller_rating = db.Column(db.String(20))  # Changed from Float
    condition = db.Column(db.String(50))
    postal_code = db.Column(db.String(20))
    categories = db.Column(db.JSON)  # Requires PostgreSQL 9.4+
    listing_date = db.Column(db.DateTime)
    location_country = db.Column(db.String(50))