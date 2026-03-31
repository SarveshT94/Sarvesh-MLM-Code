from app.db import get_cursor
from app.services.commission_engine import distribute_commission


def process_daily_commissions():
    """
    Daily Commission Automation
    """

    processed = 0

    with get_cursor() as cur:

        cur.execute("""
            SELECT id
            FROM users
            WHERE is_active = TRUE
        """)

        users = cur.fetchall()

    for user in users:

        user_id = user["id"]

        try:

            distribute_commission(user_id, 100)

            processed += 1

        except Exception as e:

            print("Commission Error:", user_id, str(e))

    return processed
