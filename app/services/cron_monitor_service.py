from app.db import get_cursor
from datetime import datetime


def log_cron_job(job_name, status, message=None):

    cursor = get_cursor()

    cursor.execute(
        """
        INSERT INTO cron_job_logs
        (job_name, status, message, executed_at)
        VALUES (%s, %s, %s, %s)
        """,
        (
            job_name,
            status,
            message,
            datetime.utcnow()
        )
    )
