import threading
import time
from venv import logger
from app.monitor.service import MonitoringService

class MonitorScheduler:
    def __init__(self):
        self.monitor = MonitoringService()
        self._running = False
    
    def start(self):
        """Start the monitoring scheduler"""
        self._running = True
        thread = threading.Thread(target=self.run_loop)
        thread.daemon = True
        thread.start()
    
    def run_loop(self):
        """Main scheduler loop"""
        while self._running:
            try:
                self.monitor.run_checks()
            except Exception as e:
                logger.error(f"Scheduler error: {str(e)}")
            time.sleep(60)  # Check every minute
    
    def stop(self):
        """Stop the monitoring scheduler"""
        self._running = False 