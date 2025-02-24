import click
import time
from .core import scheduler

@click.command("start-scheduler")
def start_scheduler():
    try:
        scheduler.start()
        click.echo("Scheduler running. Ctrl+C to stop")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        click.echo("Scheduler stopped")