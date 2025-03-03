from datetime import datetime, timedelta, timezone
from app.jobs.check_user_subscriptions import check_subscriptions
from app.models import Query, User
from app.utils.query_helpers import update_user_usage

def test_expired_user_downgrade(db_session):
    user = User(
        email='expired@test.com',
        tier={'tier': 'individual', 'query_limit': 1500},
        subscription_valid_until=datetime.now(timezone.utc) - timedelta(days=1),
        auto_renew=False
    )
    db_session.add(user)
    db_session.commit()

    # Initial state
    assert user.tier['tier'] == 'individual'
    
    check_subscriptions()
    
    # Refresh user
    db_session.refresh(user)
    assert user.tier['tier'] == 'free'
    assert user.tier['query_limit'] == 0
    assert user.subscription_valid_until > datetime.utcnow()

def test_autorenew_user_extension(db_session):
    user = User(
        email='autorenew@test.com',
        tier={'tier': 'business', 'query_limit': 4000},
        subscription_valid_until=datetime.now(timezone.utc) - timedelta(hours=1),
        auto_renew=True
    )
    db_session.add(user)
    db_session.commit()
    
    check_subscriptions()
    
    db_session.refresh(user)
    assert user.tier['tier'] == 'business'
    assert user.tier['query_limit'] == 4000
    assert user.subscription_valid_until > datetime.utcnow()

def test_requested_change(db_session):
    user = User(
        email='change@test.com',
        tier={'tier': 'old', 'query_limit': 100},
        subscription_valid_until=datetime.now(timezone.utc) - timedelta(days=2),
        auto_renew=True,
        requested_change={'tier': 'new', 'query_limit': 200}
    )
    db_session.add(user)
    db_session.commit()
    
    check_subscriptions()
    
    db_session.refresh(user)
    assert user.tier['tier'] == 'new'
    assert user.requested_change is None

#TEST PAUSING QUERIES
#********************

def test_pause_queries_on_downgrade(db_session):
    # Create user with active queries
    user = User(
        email='queries@test.com',
        tier={'tier': 'individual', 'query_limit': 1500},
        subscription_valid_until=datetime.now(timezone.utc) - timedelta(days=1),
        auto_renew=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create 5 active queries
    for i in range(5):
        query = Query(
            user_id=user.id,
            is_active=True,
            keywords=f"test {i}",
            check_interval=5
        )
        db_session.add(query)
        update_user_usage(user, query, 'add')
    db_session.commit()

    # Check if queries are active
    active = Query.query.filter_by(user_id=user.id, is_active=True).count()
    print(f"Active queries: {active}")
    assert active == 5

    # Change user tier to free
    user.requested_change = {'tier': 'test', 'query_limit': 400}
    db_session.commit()
    
    check_subscriptions()
    
    # Verify queries paused
    paused = Query.query.filter_by(user_id=user.id, is_active=False).count()
    assert paused == 4

def test_pause_exceeding_queries(db_session):
    user = User(
        email='exceed@test.com',
        tier={'tier': 'individual', 'query_limit': 1500},
        subscription_valid_until=datetime.now(timezone.utc) - timedelta(days=30),
        auto_renew=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create 3 active queries (over free tier limit)
    for i in range(3):
        query = Query(
            user_id=user.id,
            is_active=True,
            keywords=f"test {i}",
            check_interval=5
        )
        db_session.add(query)
        update_user_usage(user, query, 'add')
    db_session.commit()

    #downgrade user to free tier
    user.requested_change = {'tier': 'free', 'query_limit': 0}
    db_session.commit()
    
    check_subscriptions()

    # Verify oldest queries paused
    active = Query.query.filter_by(user_id=user.id, is_active=True).count()
    assert active == 0  # Free tier allows 0 active queries

#TEST USER SELECTION
#********************

def test_only_expired_users_processed(db_session):
    # Expired user
    expired = User(
        email='expired2@test.com',
        subscription_valid_until=datetime.now(timezone.utc) - timedelta(days=1),
        auto_renew=True,
        tier={'tier': 'individual', 'query_limit': 1500}
    )
    
    # Active user
    active = User(
        email='active2@test.com',
        subscription_valid_until=datetime.now(timezone.utc) + timedelta(days=1),
        auto_renew=True,
        tier={'tier': 'individual', 'query_limit': 1500}
    )
    
    db_session.add(expired)
    db_session.add(active)
    db_session.commit()

    #downgrade both users to free tier
    expired.requested_change = {'tier': 'free', 'query_limit': 0}
    active.requested_change = {'tier': 'free', 'query_limit': 0}
    db_session.commit()
    
    check_subscriptions()
    
    # Verify only expired user processed
    db_session.refresh(expired)
    db_session.refresh(active)
    assert expired.tier['tier'] == 'free'
    assert active.tier['tier'] != 'free'

def test_multiple_expired_users(db_session):
    # Create 10 expired users
    users = []
    for i in range(10):
        user = User(
            email=f'user{i}@test.com',
            tier={'tier': f'tier{i}', 'query_limit': 100},
            subscription_valid_until=datetime.now(timezone.utc) - timedelta(days=1),
            auto_renew=False
        )
        users.append(user)
        db_session.add(user)
    db_session.commit()
    
    check_subscriptions()
    
    # Verify all were processed
    for user in users:
        db_session.refresh(user)
        assert user.tier['tier'] == 'free'