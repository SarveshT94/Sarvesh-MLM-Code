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
    stats = {
        "total_users": 0,
        "active_users": 0,
        "total_commissions": 0.00,
        "withdraw_requests": 0
    }

    try:
        with get_cursor() as cur:
            # 1. Total Users
            cur.execute("SELECT COUNT(*) as count FROM users")
            result = cur.fetchone()
            if result:
                stats["total_users"] = result['count']

            # 2. Active Users
            cur.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
            result = cur.fetchone()
            if result:
                stats["active_users"] = result['count']

            # 3. Total Commissions Paid (🔥 FIXED: Casts to numeric and sums BOTH legacy and new tables)
            cur.execute("""
                SELECT 
                    (SELECT COALESCE(SUM(amount::numeric), 0) FROM commissions) +
                    (SELECT COALESCE(SUM(amount::numeric), 0) FROM wallet_ledger WHERE transaction_type ILIKE '%commission%')
                AS grand_total
            """)
            result = cur.fetchone()
            if result and result['grand_total']:
                stats["total_commissions"] = float(result['grand_total'])

            # 4. Pending Withdraw Requests (🔥 FIXED: Bulletproof casing check)
            cur.execute("SELECT COUNT(*) as count FROM withdraw_requests WHERE LOWER(status) IN ('pending', 'processing')")
            result = cur.fetchone()
            if result:
                stats["withdraw_requests"] = result['count']

    except Exception as e:
        # If it crashes, this will loudly tell us exactly WHY in your terminal
        print(f"\n{'='*50}\n🔥 DASHBOARD TILE CRASH:\n{str(e)}\n{'='*50}\n")

    return stats
