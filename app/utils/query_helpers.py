from decimal import Decimal, InvalidOperation
from app import db
from app.models import Query


def calculate_daily_runs(check_interval):
    """Calculate daily runs based on check interval in minutes"""
    if check_interval <= 0:
        raise ValueError("Check interval must be positive")
    return (24 * 60) // check_interval

def update_user_usage(user, query, operation='add'):
    """Update user's query usage when adding/removing/pausing queries"""
    try:
        daily_runs = calculate_daily_runs(query.check_interval)
        
        if operation == 'add':
            new_usage = user.query_usage + daily_runs
            if new_usage > max(user.tier['query_limit'] - 300, 0):
                # Calculate how much they need to upgrade
                needed = new_usage - user.query_usage
                raise ValueError(
                    f"Activating this query would exceed your daily limit by {needed}. "
                    f"Current: {user.query_usage}/{max(user.tier['query_limit']-300, 0)}. "
                    "Please upgrade your plan."
                )
            user.query_usage = new_usage
        elif operation == 'remove':
            user.query_usage = max(0, user.query_usage - daily_runs)
        else:
            raise ValueError("Invalid operation")
        
        db.session.commit()
        return True
    except (ValueError, InvalidOperation) as e:
        db.session.rollback()
        raise e
    
def pause_queries_exceeding_limit(user):
    """Pause queries that would exceed the user's query limit"""
    
    print("Running pause_queries_exceeding_limit")
    queries = Query.query.filter_by(user=user, is_active=True).order_by(Query.created_at.desc()).all()
    print(f"Active queries for user {user.id}: {queries}")
    paused_queries = []
    print(f"User query usage: {user.query_usage}")
    print(f"User tier query limit: {user.tier['query_limit']}")

    for query in queries:
        if user.query_usage <= user.tier['query_limit']:
            break
        print(f"Pausing query {query.id}")
        query.is_active = False
        user.query_usage = user.query_usage - calculate_daily_runs(query.check_interval)
        print(f"User query usage after pausing: {user.query_usage} compared to limit of {user.tier['query_limit']}")
        paused_queries.append(query)
        db.session.commit()
    
    # return the number of queries paused
    print(f"Paused {len(paused_queries)} queries")
    return len(paused_queries)