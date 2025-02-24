from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine

# Create engine for job store
jobstore_engine = create_engine('sqlite:///instance/app.db')

# Configure job store
jobstores = {
    'default': SQLAlchemyJobStore(
        engine=jobstore_engine,
        tablename='apscheduler_jobs'
    )
}

# Initialize scheduler
scheduler = BackgroundScheduler(jobstores=jobstores)