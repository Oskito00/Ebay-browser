import click
from flask.cli import with_appcontext
from app.scheduler.scheduler import SchedulerManager
from app.scheduler import create_scheduler_app
import time

@click.command("start-scheduler")
@with_appcontext
def start_scheduler():
    """Start the scheduler service"""
    # Create minimal app
    scheduler_app = create_scheduler_app()
    
    # Initialize manager
    manager = SchedulerManager(scheduler_app)
    
    try:
        click.echo("Starting scheduler...")
        manager.start()
        click.echo("Scheduler running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.scheduler.shutdown()
        click.echo("\nScheduler stopped")

@click.command("init-scheduler")
@with_appcontext
def init_scheduler():
    """Create scheduler tables in main database"""
    from sqlalchemy import text
    from app.extensions import db
    
    # Create tables in existing app.db
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS apscheduler_jobs (
                id VARCHAR(191) NOT NULL,
                next_run_time FLOAT,
                job_state BLOB NOT NULL,
                PRIMARY KEY (id)
            )
        """))
        conn.commit()
    
    click.echo("Created scheduler tables in app.db")