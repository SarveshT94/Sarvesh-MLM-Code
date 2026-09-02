from app.db import get_cursor
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def get_dashboard_stats():
    """
    Enterprise Analytics Engine.
    """
    stats = {
        "total_users": 0,
        "active_users": 0,
        "total_revenue": 0.00,
        "total_commissions": 0.00,
        "withdraw_requests": 0,
        "pending_payout": 0.00,
        "total_wallet_balance": 0.00,
    }

    try:
        with get_cursor() as cur:

            # 1. Total Users
            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            stats["total_users"] = int(cur.fetchone()["cnt"])

            # 2. Active Users
            cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_active = TRUE")
            stats["active_users"] = int(cur.fetchone()["cnt"])

            # 3. Total Revenue
            cur.execute("""
                SELECT COALESCE(SUM(amount::numeric), 0) AS val
                FROM user_packages
            """)
            stats["total_revenue"] = float(cur.fetchone()["val"])

            # 4. Total Commissions
            cur.execute("""
                SELECT COALESCE(SUM(amount::numeric), 0) AS val
                FROM commissions
            """)
            stats["total_commissions"] = float(cur.fetchone()["val"])

            # 5. Pending Withdraw Requests
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM withdraw_requests
                WHERE LOWER(status) IN ('pending', 'processing')
            """)
            stats["withdraw_requests"] = int(cur.fetchone()["cnt"])

            # 6. Pending Payout Amount
            cur.execute("""
                SELECT COALESCE(SUM(amount::numeric), 0) AS val
                FROM withdraw_requests
                WHERE LOWER(status) = 'pending'
            """)
            stats["pending_payout"] = float(cur.fetchone()["val"])

            # 7. Total Wallet Balance (THE FIX)
            cur.execute("""
                SELECT COALESCE(SUM(
                    CASE 
                        WHEN LOWER(transaction_type) LIKE '%debit%' THEN -ABS(amount::numeric)
                        ELSE ABS(amount::numeric)
                    END
                ), 0) AS val
                FROM wallet_ledger
            """)
            stats["total_wallet_balance"] = float(cur.fetchone()["val"])

    except Exception as e:
        logger.error(f"Dashboard stats error: {str(e)}")

    return stats
