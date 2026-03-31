from app.db import get_cursor
from datetime import datetime


def log_admin_action(
    admin_id,
    action,
    target_user_id=None,
    description=None
):
    """
    Central Admin Activity Logger
    """

    cursor = get_cursor()

    cursor.execute(
        """
        INSERT INTO admin_logs
        (admin_id, action, target_user_id, description, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            admin_id,
            action,
            target_user_id,
            description,
            datetime.utcnow()
        )
    )
