from datetime import datetime
from app import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    telegram_chat_id = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    queries = db.relationship('Query', backref='user', lazy=True)

class Query(db.Model):
    __tablename__ = 'queries'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID
    keywords = db.Column(db.String(128), nullable=False)
    filters = db.Column(db.JSON)  # {min_price, max_price, condition, etc}
    check_interval = db.Column(db.Integer, default=60)  # Seconds
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    items = db.relationship('Item', backref='query', lazy=True)

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    ebay_item_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(255))
    price = db.Column(db.Numeric(10,2))
    currency = db.Column(db.String(3))
    condition = db.Column(db.String(50))
    url = db.Column(db.String(512))
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    query_id = db.Column(db.String(36), db.ForeignKey('queries.id'), nullable=False) 