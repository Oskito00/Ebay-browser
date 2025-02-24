from app.jobs.query_check import full_scrape_job, recent_scrape_job
from .core import get_scheduler
from app.models import Query
from app import db
import json

class SchedulerManager:
    def __init__(self, app):
        self.app = app
        self.scheduler = get_scheduler()
    
    def start_sync(self):
        """Check queries every 30 seconds"""
        self.scheduler.add_job(
            self.sync_jobs,
            'interval',
            seconds=30,
            id='query_sync'
        )
    
    def sync_jobs(self):
        with self.app.app_context():
            # Get all active queries
            queries = db.session.query(Query).all()
            
            for query in queries:
                if query.needs_scheduling:
                    self._add_jobs(query)
                else:
                    self._remove_jobs(query)
    
    def _add_jobs(self, query):
        # Store query ID as JSON-serializable argument
        self.scheduler.add_job(
            'app.jobs.job_management:full_scrape_job',
            'interval',
            hours=24,
            kwargs={'query_id': query.id},  # Use kwargs for JSON
            id=f'full_{query.id}',
            replace_existing=True
        )
        
        # Recent scrape job
        self.scheduler.add_job(
            recent_scrape_job,
            'interval',
            minutes=query.check_interval,
            args=[query.id],
            id=f'recent_{query.id}',
            replace_existing=True
        )
        query.needs_scheduling = False
        db.session.commit()
    
    def _remove_jobs(self, query):
        try:
            self.scheduler.remove_job(f'full_{query.id}')
            self.scheduler.remove_job(f'recent_{query.id}')
        except LookupError:
            pass