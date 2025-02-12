import click
from flask import current_app
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError

@click.command("start-scheduler")
def start_scheduler():
    """Run the APScheduler in a dedicated process"""
    scheduler = BackgroundScheduler(
        jobstores={'default': current_app.scheduler_jobstore},
        job_defaults={
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 60
        },
        timezone=current_app.config['TIMEZONE']
    )
    
    # Add jobs
    with current_app.app_context():
        from app.models import Query
        for query in Query.query.all():
            scheduler.add_job(
                id=f'query_{query.id}',
                func='app.jobs.query_jobs:check_query',
                args=[query.id],
                trigger='interval',
                minutes=query.check_interval,
                replace_existing=True
            )
    
    scheduler.start()
    click.echo("Scheduler started in dedicated process")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        scheduler.shutdown()

def add_single_job(query_id):
    with current_app.app_context():
        from app.models import Query
        query = Query.query.get(query_id)
        
        current_app.scheduler.add_job(
            id=f'query_{query.id}',
            func='app.jobs.query_jobs:check_query',
            args=[query.id],
            trigger='interval',
            minutes=query.check_interval,
            replace_existing=True
        ) 

def remove_single_job(query_id):
    with current_app.app_context():
        job_id = f'query_{query_id}'
        try:
            current_app.scheduler.remove_job(job_id)
            current_app.logger.info(f"Removed job {job_id}")
        except JobLookupError:
            current_app.logger.warning(f"Job {job_id} not found") 