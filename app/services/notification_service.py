from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def create_notification(user_id, title, message, notif_type="system"):
    """
    BUG FIXED #6:
    Was using cursor = get_cursor() directly — crashes.
    Fixed to use `with get_cursor() as cur:` pattern.
    """
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO notifications
                (user_id, type, title, message, is_read, created_at)
                VALUES (%s, %s, %s, %s, FALSE, NOW())
            """, (user_id, notif_type, title, message))
    except Exception as e:
        logger.error(f"Failed to create notification for user {user_id}: {str(e)}")


def get_user_notifications(user_id, limit=20):
    """
    BUG FIXED #6: Was using cursor = get_cursor() directly.
    """
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, title, message, type, is_read, created_at
                FROM notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Failed to fetch notifications for user {user_id}: {str(e)}")
        return []


def mark_notification_read(notification_id, user_id=None):
    """
    BUG FIXED #13:
    notification_routes.py was calling mark_notification_read(notification_id, user_id)
    with 2 args but the old function only accepted 1.
    Fixed: user_id is now an optional second argument (used to verify ownership).
    """
    try:
        with get_cursor() as cur:
            if user_id:
                cur.execute("""
                    UPDATE notifications
                    SET is_read = TRUE
                    WHERE id = %s AND user_id = %s
                """, (notification_id, user_id))
            else:
                cur.execute("""
                    UPDATE notifications SET is_read = TRUE WHERE id = %s
                """, (notification_id,))
    except Exception as e:
        logger.error(f"Failed to mark notification {notification_id} as read: {str(e)}")


def mark_all_read(user_id):
    """Mark all notifications as read for a user."""
    try:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE notifications SET is_read = TRUE WHERE user_id = %s
            """, (user_id,))
    except Exception as e:
        logger.error(f"Failed to mark all notifications read for user {user_id}: {str(e)}")


def get_unread_count(user_id):
    """Get unread notification count for badge display."""
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt FROM notifications
                WHERE user_id = %s AND is_read = FALSE
            """, (user_id,))
            return int(cur.fetchone()["cnt"])
    except Exception as e:
        logger.error(f"Unread count error for user {user_id}: {str(e)}")
        return 0
