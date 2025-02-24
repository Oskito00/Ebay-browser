from flask import Flask
from config import SchedulerConfig
from app.extensions import db
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import text

def create_scheduler_app():
    app = Flask(__name__)
    app.config.from_object(SchedulerConfig)
    print(f"Engine URL: {db.get_engine().url}")

    
    # Initialize only DB
    db.init_app(app)
    
    with app.app_context():
        # Initialize metadata
        jobstore = SQLAlchemyJobStore(engine=db.get_engine())
        
        # Use connection context
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
        
        app.scheduler_jobstore = jobstore
    
    print(type(app.scheduler_jobstore))
    
    return app