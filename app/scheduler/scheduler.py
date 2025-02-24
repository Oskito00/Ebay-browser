from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.models import Query
from app import db
from app.jobs.job_management import full_scrape_job, recent_scrape_job


class SchedulerManager:
    def __init__(self, app):
        self.app = app
        self.scheduler = BackgroundScheduler(
            jobstores={
                'default': SQLAlchemyJobStore(
                    engine=db.get_engine(),
                    tablename='apscheduler_jobs'
                )
            },
            timezone=app.config.get('SCHEDULER_TIMEZONE', 'UTC')
        )
        
    def start(self):
        """Start the scheduler and sync jobs"""
        with self.app.app_context():
            self.scheduler.start()
            self.schedule_sync_jobs()
            
    def schedule_sync_jobs(self):
        """Schedule regular sync job"""
        self.scheduler.add_job(
            self.sync_jobs,
            'interval',
            seconds=30,
            id='sync_jobs'
        )
        
    def sync_jobs(self):
        """Main sync logic"""
        with self.app.app_context():
            # Add new jobs
            new_queries = Query.query.filter(
                Query.needs_scheduling == True,
                Query.is_active == True
            ).all()
            
            for query in new_queries:
                self.add_job(query)
                query.needs_scheduling = False
                db.session.commit()
                
            # Remove orphaned jobs
            active_ids = [q.id for q in Query.query.all()]
            for job in self.scheduler.get_jobs():
                if job.id.startswith(('full_', 'recent_')):
                    q_id = int(job.id.split('_')[1])
                    if q_id not in active_ids:
                        self.remove_job(job.id)
                        
    def add_job(self, query):
        """Add jobs for a new query"""
        self.scheduler.add_job(
            full_scrape_job,
            'interval',
            hours=24,
            args=[query.id],
            misfire_grace_time=300,  # 5 minutes
            max_instances=1,
            id=f'full_{query.id}'
        )
        
        self.scheduler.add_job(
            recent_scrape_job,
            'interval',
            minutes=query.check_interval,
            args=[query.id],
            misfire_grace_time=120,  # 2 minutes
            max_instances=1,
            id=f'recent_{query.id}'
        )
        
    def remove_job(self, job_id):
        """Remove a job by ID"""
        try:
            self.scheduler.remove_job(job_id)
        except LookupError:
            pass