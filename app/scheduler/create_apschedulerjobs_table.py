import sqlite3

def init_jobs_table():
    """Creates the apscheduler_jobs table if it doesn't exist"""
    conn = None
    try:
        conn = sqlite3.connect('instance/app.db')
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS apscheduler_jobs (
                    id TEXT PRIMARY KEY,
                    next_run_time FLOAT,
                    job_state BLOB
                 )''')
                 
        conn.commit()
        print("Created apscheduler_jobs table")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

# Initialize when module is imported
init_jobs_table()