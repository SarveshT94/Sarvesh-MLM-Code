from app.db import get_cursor


def get_commission_logs(limit=100, offset=0):
    """
    Fetch commission logs for admin panel
    """

    with get_cursor() as cur:

        cur.execute("""
            SELECT
                c.id,
                c.earner_id,
                c.from_user_id,
                c.level,
                c.amount,
                c.commission_type,
                c.created_at,
                u.full_name AS earner_name,
                f.full_name AS from_user_name
            FROM commissions c
            JOIN users u ON u.id = c.earner_id
            JOIN users f ON f.id = c.from_user_id
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))

        logs = cur.fetchall()

    return logs
