from app.db import get_cursor


def get_system_health():

    with get_cursor() as cur:

        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        active_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM withdraw_requests WHERE status='pending'")
        pending_withdrawals = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM wallet_ledger")
        total_wallet_volume = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM commission_logs")
        total_commission = cur.fetchone()[0]

    return {
        "total_users": total_users,
        "active_users": active_users,
        "pending_withdrawals": pending_withdrawals,
        "wallet_volume": total_wallet_volume,
        "commission_paid": total_commission
    }
