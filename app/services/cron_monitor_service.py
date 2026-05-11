from app.db import get_cursor
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def log_cron_job(job_name, status, message=None):
    """
    BUG FIXED #5:
    Was using cursor = get_cursor() directly — crashes.
    Fixed to use `with get_cursor() as cur:` pattern.
    """
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO cron_job_logs
                (job_name, status, message, executed_at)
                VALUES (%s, %s, %s, %s)
            """, (job_name, status, message, datetime.utcnow()))
    except Exception as e:
        logger.error(f"Failed to log cron job '{job_name}': {str(e)}")


def get_cron_logs(limit=50):
    """Fetch recent cron job logs for admin dashboard."""
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT job_name, status, message, executed_at
                FROM cron_job_logs
                ORDER BY executed_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Cron log fetch error: {str(e)}")
        return []
