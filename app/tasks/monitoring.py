import logging
from app.monitor.service import MonitoringService
from app import app

logger = logging.getLogger(__name__)

def start_monitoring():
    """Main entry point for executing monitoring checks"""
    with app.app_context():
        try:
            logger.info("Starting monitoring checks...")
            
            # Initialize and run monitoring service
            service = MonitoringService()
            service.run_checks()
            
            logger.info("Monitoring checks completed successfully")
            return True
        except Exception as e:
            logger.error(f"Monitoring failed: {str(e)}", exc_info=True)
            return False