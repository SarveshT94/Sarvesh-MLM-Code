from app.db import get_cursor
from decimal import Decimal

# -----------------------------------
# System Health & Analytics Dashboard
# -----------------------------------
def get_dashboard_stats():
    """
    Enterprise Analytics Engine:
    Maps perfectly to dashboard.html template variables.
    """
    # 1. Set the exact keys expected by the dashboard.html template
    stats = {
        "total_users": 0,
        "active_users": 0,
        "total_commissions": Decimal('0.00'),
        "withdraw_requests": 0
    }

    try:
        with get_cursor() as cur:
            # 2. Total Users (Counts EVERYONE, including Admins)
            cur.execute("SELECT COUNT(*) as count FROM users")
            result = cur.fetchone()
            if result:
                stats["total_users"] = result['count']

            # 3. Active Users (Counts EVERYONE who is active)
            cur.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
            result = cur.fetchone()
            if result:
                stats["active_users"] = result['count']

            # 4. Total Commissions Paid
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) as total 
                FROM wallet_ledger 
                WHERE transaction_type = 'commission_credit'
            """)
            result = cur.fetchone()
            if result:
                stats["total_commissions"] = Decimal(str(result['total']))

            # 5. Pending Withdraw Requests
            cur.execute("SELECT COUNT(*) as count FROM withdraw_requests WHERE status = 'Pending'")
            result = cur.fetchone()
            if result:
                stats["withdraw_requests"] = result['count']

    except Exception as e:
        # If the DB query fails, print the error to the terminal but STILL return the default 0s 
        # so the dashboard doesn't crash completely.
        print(f"🔥 Dashboard Stats Error: {str(e)}")

    return stats
