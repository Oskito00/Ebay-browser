from datetime import datetime, timedelta, timezone
from app import db
from app.models import User, Query
from app.utils.query_helpers import pause_queries_exceeding_limit

# def check_subscriptions():
#     """Check and enforce subscription expiration"""
#     expired_users = User.query.filter(
#         User.subscription_valid_until < datetime.now(timezone.utc)
#     ).all()

#     print(f"Expired users: {expired_users}")

#     for user in expired_users:
#         # Check if auto renew is enabled
#         if user.auto_renew == False:
#             #Sets the user to free tier
#             user.tier = {'tier': 'free', 'query_limit': 0}
#             user.subscription_valid_until = datetime.now(timezone.utc) + timedelta(days=30)
#             # Pause all queries
#             pause_queries_exceeding_limit(user)
#         elif user.requested_change:
#             print(f"User requested change: {user.requested_change}")

#             #Sets the user to the requested tier
#             user.tier = user.requested_change
#             user.subscription_valid_until = datetime.now(timezone.utc) + timedelta(days=30)
#             # Pause queries that would exceed the new tier limit
#             pause_queries_exceeding_limit(user)
#             user.requested_change = None

#         else:
#             #Keeps the user on the same tier, updates the subscription valid until date
#             user.subscription_valid_until = datetime.now(timezone.utc) + timedelta(days=30)
        
#         db.session.add(user)
    
#     db.session.commit()

