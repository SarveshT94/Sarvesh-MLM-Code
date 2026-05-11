from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def get_system_health():
    """
    BUG FIXED #16: fetchone()[0] crashes with RealDictCursor.
    All fetchone() calls now use named dict keys.

    BUG FIXED #27: was querying 'commission_logs' table which doesn't exist.
    Correct table is 'commissions'.
    """
    with get_cursor() as cur:

        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        total_users = int(cur.fetchone()["cnt"])

        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_active = TRUE")
        active_users = int(cur.fetchone()["cnt"])

        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM withdraw_requests WHERE status = 'pending'
        """)
        pending_withdrawals = int(cur.fetchone()["cnt"])

        cur.execute("SELECT COALESCE(SUM(amount), 0) AS val FROM wallet_ledger")
        total_wallet_volume = float(cur.fetchone()["val"])

        # FIXED: was querying commission_logs (doesn't exist). Correct table = commissions
        cur.execute("SELECT COALESCE(SUM(amount), 0) AS val FROM commissions")
        total_commission = float(cur.fetchone()["val"])

        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_active = TRUE")
        active_count = int(cur.fetchone()["cnt"])

        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS val FROM user_packages
        """)
        total_revenue = float(cur.fetchone()["val"])

    return {
        "total_users": total_users,
        "active_users": active_count,
        "pending_withdrawals": pending_withdrawals,
        "wallet_volume": total_wallet_volume,
        "commission_paid": total_commission,
        "total_revenue": total_revenue,
    }
