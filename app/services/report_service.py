from app.db import get_cursor

def get_financial_report():
    """
    MLM Financial Summary Report - Exhaustive Key Mapping
    """
    report = {}

    with get_cursor() as cur:

        # 1. Revenue
        cur.execute("SELECT COALESCE(SUM(amount::numeric), 0) AS val FROM user_packages")
        revenue = float(cur.fetchone()["val"])
        report["total_revenue"] = revenue
        report["revenue"] = revenue

        # 2. Commissions
        cur.execute("SELECT COALESCE(SUM(amount::numeric), 0) AS val FROM commissions")
        commissions = float(cur.fetchone()["val"])
        report["total_commission"] = commissions

        # 3. Payouts (Money Distributed)
        cur.execute("""
            SELECT COALESCE(SUM(amount::numeric), 0) AS val 
            FROM withdraw_requests 
            WHERE LOWER(status) = 'approved'
        """)
        payouts = float(cur.fetchone()["val"])
        report["approved_withdraw"] = payouts
        report["total_payouts"] = payouts
        report["distributed_payouts"] = payouts

        # 4. Liability (Pending Wallet Balances)
        # HTML likely looks for: liability, total_liability, or wallet_total
        cur.execute("SELECT COALESCE(SUM(amount::numeric), 0) AS val FROM wallet_ledger")
        liability = float(cur.fetchone()["val"])
        report["wallet_total"] = liability
        report["liability"] = liability
        report["total_liability"] = liability
        report["pending_wallet_balances"] = liability

        # 5. TDS & Admin Profit
        # HTML likely looks for: admin_fees, admin_profit, tds_collected
        tds = commissions * 0.05
        profit = revenue - commissions
        
        report["tds_collected"] = tds
        report["total_tds"] = tds
        
        report["admin_profit"] = profit
        report["admin_fees"] = profit
        report["profit"] = profit
        report["system_profit"] = profit

        # 6. User Stats
        cur.execute("SELECT COUNT(*) AS count FROM users")
        report["total_users"] = cur.fetchone()["count"]

        cur.execute("SELECT COUNT(*) AS count FROM users WHERE is_active = TRUE")
        report["active_users"] = cur.fetchone()["count"]

    return report
