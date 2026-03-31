from app.db import get_cursor


def get_financial_report():
    """
    MLM Financial Summary Report
    """

    report = {}

    with get_cursor() as cur:

        # Total Users
        cur.execute("""
            SELECT COUNT(*) AS total_users
            FROM users
        """)
        report["total_users"] = cur.fetchone()["total_users"]

        # Active Users
        cur.execute("""
            SELECT COUNT(*) AS active_users
            FROM users
            WHERE is_active = TRUE
        """)
        report["active_users"] = cur.fetchone()["active_users"]

        # Total Commission Paid
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS total_commission
            FROM commissions
        """)
        report["total_commission"] = float(cur.fetchone()["total_commission"])

        # Withdraw Approved
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS approved_withdraw
            FROM withdraw_requests
            WHERE status='approved'
        """)
        report["approved_withdraw"] = float(cur.fetchone()["approved_withdraw"])

        # Withdraw Pending
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS pending_withdraw
            FROM withdraw_requests
            WHERE status='pending'
        """)
        report["pending_withdraw"] = float(cur.fetchone()["pending_withdraw"])

        # Total Wallet Balance
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS wallet_total
            FROM wallet_ledger
            WHERE transaction_type='commission_credit'
        """)
        report["wallet_total"] = float(cur.fetchone()["wallet_total"])

    return report
