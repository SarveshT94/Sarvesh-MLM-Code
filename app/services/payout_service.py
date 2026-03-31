from app.db import get_db_connection


def get_payout_report():

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                u.id,
                u.full_name,
                u.email,
                COALESCE(SUM(c.amount),0) as total_commission
            FROM users u
            LEFT JOIN commissions c
            ON u.id = c.earner_id
            GROUP BY u.id
            ORDER BY total_commission DESC
        """)

        rows = cur.fetchall()

        return rows

    finally:

        cur.close()
        conn.close()
