from apscheduler.schedulers.background import BackgroundScheduler
from flask import app, current_app
from sqlalchemy import and_
from app import db
import logging
from datetime import datetime, timedelta, timezone

from app.models import Query

class SchedulerManager:
    def __init__(self, app):
        self.app = app
        self.scheduler = BackgroundScheduler(
            jobstores={'default': app.scheduler_jobstore},
            logger=logging.getLogger('apscheduler')
        )
    
    def start_polling(self, interval=30):
        self.scheduler.add_job(
            self.sync_jobs,
            'interval',
            seconds=interval,
            id='sync_jobs'
        )
    
    def sync_jobs(self):
        with self.app.app_context():
            # Process new queries
            new_queries = Query.query.filter(
                Query.needs_scheduling == True,
                Query.is_active == True
            ).all()
            
            for query in new_queries:
                self.add_job(query)
                query.needs_scheduling = False
                query.last_full_run = datetime.now(timezone.utc)
                query.next_full_run = datetime.now(timezone.utc) + timedelta(hours=24)
                db.session.commit()

            # Cleanup old jobs
            active_ids = [q.id for q in Query.query.filter_by(is_active=True).all()]
            for job in self.scheduler.get_jobs():
                if job.id.startswith(('full_', 'recent_')):
                    q_id = int(job.id.split('_')[1])
                    if q_id not in active_ids:
                        self.remove_job(q_id)
    
    
    def add_job(self, query):
        # First run immediately and every 24 hours
        self.scheduler.add_job(
            id=f'full_{query.id}',
            func='app.jobs.job_management:full_scrape_job',
            args=[query.id],
            trigger='interval',
            hours=24,
            next_run_time=datetime.now(),
            replace_existing=True
        )
        
        # Recent checks every X minutes
        self.scheduler.add_job(
            id=f'recent_{query.id}',
            func='app.jobs.job_management:recent_scrape_job',
            args=[query.id],
            trigger='interval',
            minutes=query.check_interval,
            replace_existing=True
        )
    
    def remove_job(self, query_id):
        try:
            self.scheduler.remove_job(f'query_{query_id}')
        except LookupError:
            pass
