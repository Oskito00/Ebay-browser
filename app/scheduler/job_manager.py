from datetime import datetime
from .core import scheduler
from app.models import Query
from app import db

def add_query_jobs(query_id):
    query = Query.query.get(query_id)

    # Full job - runs immediately and every 24h
    scheduler.add_job(
        'app.jobs.query_check:full_scrape_job',
        'interval',
        hours=24,
        args=[query_id],
        id=f'query_{query_id}_full',
        next_run_time=datetime.utcnow(),  # First run now
        misfire_grace_time=3600,  # 1 hour grace period
        coalesce=True  # Combine missed runs
    )
    
    # Recent job
    scheduler.add_job(
        'app.jobs.query_check:recent_scrape_job',
        'interval',
        minutes=query.check_interval,
        args=[query_id],
        id=f'query_{query_id}_recent'
    )
    
    

def remove_query_jobs(query_id):
    try:
        scheduler.remove_job(f'query_{query_id}_recent')
        scheduler.remove_job(f'query_{query_id}_full')
    except LookupError:
        pass