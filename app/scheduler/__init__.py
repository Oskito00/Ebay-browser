from flask import current_app
from app.jobs.query_check import check_queries
from .core import scheduler


def init_scheduler(flask_app):
    scheduler.flask_app = flask_app
    scheduler.add_job(
        check_queries,
        'interval',
        seconds=30,
        id='query_check',
        replace_existing=True
    )