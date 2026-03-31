from app.db import get_db_connection


def get_dashboard_stats():

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        # Total users
        cur.execute("SELECT COUNT(*) as total FROM users")
        total_users = cur.fetchone()["total"]

        # Active users
        cur.execute("SELECT COUNT(*) as total FROM users WHERE is_active = TRUE")
        active_users = cur.fetchone()["total"]

        # Today's registrations
        cur.execute("""
            SELECT COUNT(*) as total
            FROM users
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        today_registrations = cur.fetchone()["total"]

        # Total commission paid
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as total
            FROM commissions
        """)
        total_commission = cur.fetchone()["total"]

        # Withdraw requested
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as total
            FROM withdraw_requests
        """)
        withdraw_requested = cur.fetchone()["total"]

        # Withdraw approved
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as total
            FROM withdraw_requests
            WHERE status='approved'
        """)
        withdraw_approved = cur.fetchone()["total"]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "today_registrations": today_registrations,
            "total_commission_paid": total_commission,
            "withdraw_requested": withdraw_requested,
            "withdraw_approved": withdraw_approved
        }

    finally:

        cur.close()
        conn.close()
        
