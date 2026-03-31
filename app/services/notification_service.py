from app.db import get_cursor


def create_notification(user_id, title, message, notif_type="system"):

    cursor = get_cursor()

    cursor.execute("""
        INSERT INTO notifications
        (user_id, type, title, message)
        VALUES (%s, %s, %s, %s)
    """, (
        user_id,
        notif_type,
        title,
        message
    ))

def get_user_notifications(user_id):

    cursor = get_cursor()

    cursor.execute("""
        SELECT id, title, message, is_read, created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 20
    """, (user_id,))

    return cursor.fetchall()

# ✅ Wrapper / Safe fallback
def mark_notification_read(notification_id):
    """
    Temporary fallback function
    """
    return {"status": "not implemented yet", "notification_id": notification_id}
