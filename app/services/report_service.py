from app.db import get_cursor
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def get_financial_report():
    """
    Enterprise Financial Report Engine.

    BUGS FIXED:
    - BUG #14: net_profit was adding admin_fees instead of subtracting them.
      Admin fees and TDS are DEDUCTIONS from gross profit, not additions.
      Old: net_profit = gross_profit + admin_fees   ← WRONG (inflated profits)
      New: net_profit = gross_profit - admin_fees - total_tds  ← CORRECT

    - wallet_liability now correctly sums only credit entries to avoid
      double-counting debits already reflected in the balance.
    """
    report = {}

    with get_cursor() as cur:

        # 1. Fetch dynamic rate settings (Admin Fee %, TDS %)
        cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
        settings = {
            row['setting_key']: float(row['percentage_value'])
            for row in cur.fetchall()
        }

        admin_rate = settings.get('admin_fee_percentage', 5.0) / 100
        tds_rate   = settings.get('tds_percentage', 2.0) / 100

        # 2. Total Revenue & Product Costs
        cur.execute("""
            SELECT
                COALESCE(SUM(up.amount::numeric), 0)        AS total_rev,
                COALESCE(SUM(sp.product_cost::numeric), 0)  AS total_cost
            FROM user_packages up
            JOIN subscription_plans sp ON up.package_id = sp.id
        """)
        sales_data    = cur.fetchone()
        revenue       = float(sales_data["total_rev"])
        product_costs = float(sales_data["total_cost"])
        report["total_revenue"]  = revenue
        report["product_costs"]  = product_costs

        # 3. Total Commissions Paid
        cur.execute("""
            SELECT COALESCE(SUM(amount::numeric), 0) AS val
            FROM commissions
        """)
        commissions = float(cur.fetchone()["val"])
        report["total_commissions"] = commissions

        # 4. Gross Profit
        report["gross_profit"] = revenue - product_costs - commissions

        # 5. Approved Payout Volume (basis for fee/TDS calculation)
        cur.execute("""
            SELECT COALESCE(SUM(amount::numeric), 0) AS total_payouts
            FROM withdraw_requests
            WHERE LOWER(status) = 'approved'
        """)
        payout_vol = float(cur.fetchone()["total_payouts"])
        report["approved_payouts"] = payout_vol

        # 6. Admin Fee & TDS (both are DEDUCTIONS)
        report["admin_fees"] = round(payout_vol * admin_rate, 2)
        report["total_tds"]  = round(payout_vol * tds_rate, 2)

        # 7. Net Profit
        # FIXED: was gross_profit + admin_fees (wrong — was inflating profit).
        # Admin fees and TDS come OUT of gross profit.
        report["net_profit"] = round(
            report["gross_profit"] - report["admin_fees"] - report["total_tds"],
            2
        )

        # 8. System Wallet Liability
        # Sum only credit-type entries (what users have earned but not withdrawn)
        # to get a true liability figure.
        cur.execute("""
            SELECT COALESCE(SUM(amount::numeric), 0) AS val
            FROM wallet_ledger
            WHERE amount > 0
        """)
        report["total_wallet_liability"] = float(cur.fetchone()["val"])

        # 9. Pending Withdrawal Liability
        cur.execute("""
            SELECT COALESCE(SUM(amount::numeric), 0) AS val
            FROM withdraw_requests
            WHERE LOWER(status) = 'pending'
        """)
        report["pending_payout_liability"] = float(cur.fetchone()["val"])

        # 10. Total Users & Active
        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        report["total_users"] = int(cur.fetchone()["cnt"])

        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_active = TRUE")
        report["active_users"] = int(cur.fetchone()["cnt"])

    logger.info(f"Financial report generated: revenue={report['total_revenue']}, "
                f"net_profit={report['net_profit']}")
    return report
