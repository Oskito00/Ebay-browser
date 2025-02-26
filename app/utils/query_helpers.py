from decimal import Decimal, InvalidOperation
from app import db

MAX_DAILY_USAGE = 4000  # Example limit: 10,000 daily calls per user

def calculate_daily_runs(check_interval):
    """Calculate daily runs based on check interval in minutes"""
    if check_interval <= 0:
        raise ValueError("Check interval must be positive")
    return (24 * 60) // check_interval

def update_user_usage(user, query, operation='add'):
    try:
        daily_runs = calculate_daily_runs(query.check_interval)
        
        if operation == 'add':
            new_usage = user.user_query_usage + daily_runs
            if new_usage > MAX_DAILY_USAGE:
                raise ValueError("This query would exceed your daily limit")
            user.user_query_usage = new_usage
        elif operation == 'remove':
            user.user_query_usage = max(0, user.user_query_usage - daily_runs)
            
        db.session.commit()
        return True
    except (ValueError, InvalidOperation) as e:
        db.session.rollback()
        raise e