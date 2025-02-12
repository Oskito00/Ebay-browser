from apscheduler.job import Job
from flask import app, current_app, jsonify
from apscheduler.schedulers.base import BaseScheduler


@app.route('/scheduler/jobs')
def list_scheduler_jobs():
    if not hasattr(current_app, 'scheduler') or not isinstance(current_app.scheduler, BaseScheduler):
        return jsonify({"error": "Scheduler not initialized"}), 500
    
    jobs = []
    for job in current_app.scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })
    return jsonify(jobs)