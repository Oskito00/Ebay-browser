from time import sleep
import click


@click.command('start-scheduler')
def start_scheduler():
    """Start the scheduler service"""
    from app.scheduler import create_scheduler_app
    app = create_scheduler_app()  # Lightweight app
    
    from app.scheduler.scheduler import SchedulerManager
    manager = SchedulerManager(app)
    manager.start_polling(interval=30)
    
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        manager.shutdown()