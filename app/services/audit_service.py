from app.db import get_cursor
import logging
import json

logger = logging.getLogger(__name__)


# =========================================================
# CREATE AUDIT LOG
# =========================================================
def log_action(
    action,
    user_id=None,
    admin_id=None,
    metadata=None,
    status="success"
):
    """
    Enterprise audit logger

    Params:
    - action (str): action name
    - user_id (int): affected user
    - admin_id (int): admin performing action
    - metadata (dict): extra info
    - status (str): success/failure
    """

    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO audit_logs
                (action, user_id, admin_id, metadata, status, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (
                action,
                user_id,
                admin_id,
                json.dumps(metadata or {}),
                status
            ))

    except Exception as e:
        logger.error(f"[AUDIT_LOG_FAIL] action={action} error={str(e)}")
