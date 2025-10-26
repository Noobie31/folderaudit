# core/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from typing import Callable, Optional
import pytz
from .logger import logger

ALLOWED_FREQUENCIES = {
    "Hourly", "Daily", "Every 2 days", "Every 3 days",
    "Weekly", "Fortnightly", "Monthly", "Every 6 months", "Yearly"
}

def start_scheduler(timezone_str: str = "Asia/Kolkata") -> BackgroundScheduler:
    """
    Initialize and start the background scheduler.
    
    Args:
        timezone_str: Timezone string (default: Asia/Kolkata)
    
    Returns:
        Running BackgroundScheduler instance
    """
    try:
        tz = pytz.timezone(timezone_str)
        sched = BackgroundScheduler(timezone=tz)
        sched.start()
        logger.info(f"Scheduler started with timezone: {timezone_str}")
        return sched
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        raise

def schedule_job(
    sched: BackgroundScheduler,
    job_id: str,
    func: Callable,
    start_date: str,
    time_str: str,
    frequency: str
) -> bool:
    """
    Schedule a job with the given parameters.
    
    Args:
        sched: BackgroundScheduler instance
        job_id: Unique job identifier
        func: Function to call
        start_date: Start date (YYYY-MM-DD) - not used in cron but kept for compatibility
        time_str: Time string (HH:MM) in 24h format
        frequency: Frequency string from ALLOWED_FREQUENCIES
    
    Returns:
        True if scheduled successfully, False otherwise
    """
    # Remove existing job if any
    try:
        sched.remove_job(job_id)
        logger.info(f"Removed existing job: {job_id}")
    except Exception:
        pass
    
    # Validate frequency
    if frequency not in ALLOWED_FREQUENCIES:
        logger.error(f"Invalid frequency: {frequency}")
        return False
    
    # Parse time
    try:
        hh, mm = [int(x) for x in time_str.split(":")]
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("Invalid time range")
    except Exception as e:
        logger.error(f"Invalid time format '{time_str}': {e}")
        return False
    
    # Schedule based on frequency
    try:
        if frequency == "Hourly":
            sched.add_job(func, "cron", id=job_id, minute=mm)
            logger.info(f"Scheduled hourly at minute {mm}")
            
        elif frequency == "Daily":
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm)
            logger.info(f"Scheduled daily at {hh:02d}:{mm:02d}")
            
        elif frequency == "Every 2 days":
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm, day="*/2")
            logger.info(f"Scheduled every 2 days at {hh:02d}:{mm:02d}")
            
        elif frequency == "Every 3 days":
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm, day="*/3")
            logger.info(f"Scheduled every 3 days at {hh:02d}:{mm:02d}")
            
        elif frequency == "Weekly":
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm, day_of_week="mon")
            logger.info(f"Scheduled weekly (Monday) at {hh:02d}:{mm:02d}")
            
        elif frequency == "Fortnightly":
            # Approximate: every 14 days
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm, day="*/14")
            logger.info(f"Scheduled fortnightly at {hh:02d}:{mm:02d}")
            
        elif frequency == "Monthly":
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm, day=1)
            logger.info(f"Scheduled monthly (1st) at {hh:02d}:{mm:02d}")
            
        elif frequency == "Every 6 months":
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm, day=1, month="1,7")
            logger.info(f"Scheduled every 6 months at {hh:02d}:{mm:02d}")
            
        elif frequency == "Yearly":
            sched.add_job(func, "cron", id=job_id, hour=hh, minute=mm, day=1, month=1)
            logger.info(f"Scheduled yearly (Jan 1st) at {hh:02d}:{mm:02d}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to schedule job: {e}", exc_info=True)
        return False

def remove_job(sched: BackgroundScheduler, job_id: str) -> bool:
    """
    Remove a scheduled job.
    
    Args:
        sched: BackgroundScheduler instance
        job_id: Job identifier to remove
    
    Returns:
        True if removed, False if not found
    """
    try:
        sched.remove_job(job_id)
        logger.info(f"Removed job: {job_id}")
        return True
    except Exception as e:
        logger.debug(f"Job not found or error removing: {e}")
        return False

def get_next_run_time(sched: BackgroundScheduler, job_id: str) -> Optional[datetime]:
    """
    Get the next run time for a scheduled job.
    
    Args:
        sched: BackgroundScheduler instance
        job_id: Job identifier
    
    Returns:
        Next run time or None if job not found
    """
    try:
        job = sched.get_job(job_id)
        if job:
            return job.next_run_time
    except Exception as e:
        logger.debug(f"Could not get next run time: {e}")
    
    return None