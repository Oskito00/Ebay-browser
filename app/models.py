from datetime import datetime, timezone
import uuid
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy import DateTime

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    telegram_chat_id = db.Column(db.String(50))
    telegram_connected = db.Column(db.Boolean, default=False)
    telegram_notifications_enabled = db.Column(db.Boolean, default=False)
    notification_preferences = db.Column(db.JSON, default={
        'price_drops': True,
        'new_items': True,
        'auction_alerts': True,
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
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    keywords = db.Column(db.String(255), nullable=False)
    check_interval = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    min_price = db.Column(db.Numeric(10,2))
    max_price = db.Column(db.Numeric(10,2))
    required_keywords = db.Column(db.String(255))
    excluded_keywords = db.Column(db.String(255))
    condition = db.Column(db.String(50))
    buying_options = db.Column(db.String(50), default='FIXED_PRICE|AUCTION')
    created_at = db.Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    filters = db.Column(db.JSON)  # {min_price, max_price, condition, etc}
    last_checked = db.Column(db.DateTime)
    limit = db.Column(db.Integer, default=200)
    total_items = db.Column(db.Integer)  # Track total found
    price_alert_threshold = db.Column(db.Float, default=5.0)  # Percentage threshold
    marketplace = db.Column(db.String(10), nullable=False, default='EBAY_GB')
    item_location = db.Column(db.String(10), nullable=False, default='GB')
    last_full_run = db.Column(DateTime(timezone=True))
    next_full_run = db.Column(DateTime(timezone=True))
    last_recent_run = db.Column(DateTime(timezone=True))
    is_active = db.Column(db.Boolean, default=True)
    needs_scheduling = db.Column(db.Boolean, default=True, index=True)

    search_items = db.relationship(
        'Item', 
        back_populates='search_query', 
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

class ItemBase(db.Model):
    __abstract__ = True  # Makes this a base class, not a table
    
    id = db.Column(db.Integer, primary_key=True)
    keywords = db.Column(db.String(255), index=True)
    ebay_id = db.Column(db.String(50), nullable=False)
    legacy_id = db.Column(db.String(50))
    title = db.Column(db.String(255))
    price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='GBP')
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
    auction_details = db.Column(db.Text)
    categories = db.Column(db.Text)
    marketplace = db.Column(db.String(20))
    images = db.Column(db.Text)

class Item(ItemBase):
    __tablename__ = 'items'
    
    query_id = db.Column(db.Integer, db.ForeignKey('queries.id'))
    search_query = db.relationship('Query', back_populates='search_items')
    auction_ending_notification_sent = db.Column(db.Boolean, default=False)
    
    __table_args__ = (
        db.UniqueConstraint('ebay_id', 'query_id', name='uq_ebay_id_query'),
    )

class LongTermItem(ItemBase):
    __tablename__ = 'long_term_items'
    
    def get_utc_now():
        return datetime.now(timezone.utc)

    recorded_at = db.Column(
        db.DateTime, 
        default=get_utc_now
    )
    
    __table_args__ = (
        db.UniqueConstraint(
            'ebay_id', 
            'keywords',
            'recorded_at',
            name='uq_ebay_keywords_time'
        ),
    )

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