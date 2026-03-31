import os
import subprocess
import logging
from datetime import datetime
from app.db import get_cursor


logger = logging.getLogger(__name__)

BACKUP_DIR = "backups"


def run_database_backup():
    """
    Create PostgreSQL backup using pg_dump in custom format (.dump)
    and store backup history in db_backup_logs table.
    """

    try:

        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.dump"
        filepath = os.path.join(BACKUP_DIR, filename)

        # Load database configuration
        db_name = os.getenv("DB_NAME", "rk_trendz_mlm")
        db_user = os.getenv("DB_USER", "postgres")
        db_host = os.getenv("DB_HOST", "localhost")
        db_password = os.getenv("DB_PASSWORD")

        # Environment variables for pg_dump
        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password

        # pg_dump command (custom format)
        command = [
            "pg_dump",
            "-h", db_host,
            "-U", db_user,
            "-d", db_name,
            "-F", "c",  # Custom dump format
            "-f", filepath
        ]

        # Run pg_dump
        subprocess.run(command, check=True, env=env)

        # Log success in database
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO db_backup_logs
                (backup_file, status)
                VALUES (%s, %s)
            """, (filename, "success"))

        logger.info(f"Database backup created successfully: {filename}")

        return {
            "status": "success",
            "file": filename
        }

    except Exception as e:

        logger.error(f"Database backup failed: {str(e)}")

        # Log failure in database
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO db_backup_logs
                (backup_file, status)
                VALUES (%s, %s)
            """, ("backup_failed", "error"))

        raise e


def get_backup_history():
    """
    Fetch last 20 backup records for admin dashboard.
    """

    with get_cursor() as cursor:

        cursor.execute("""
            SELECT id, backup_file, status, created_at
            FROM db_backup_logs
            ORDER BY created_at DESC
            LIMIT 20
        """)

        rows = cursor.fetchall()

    return rows
