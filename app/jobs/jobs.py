from app.jobs.query_check import full_scrape_job
from app.scheduler.core import get_scheduler

def add_query_job(query_id):
    scheduler = get_scheduler()  # Access global instance
    scheduler.add_job(
        full_scrape_job,
        'interval',
        hours=24,
        args=[query_id],
        id=f'full_{query_id}'
    )