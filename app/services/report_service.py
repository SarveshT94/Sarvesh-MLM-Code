from app.db import get_cursor

def get_financial_report():
    report = {}
    with get_cursor() as cur:
        # 1. FETCH SOFT-CODED SETTINGS (Admin Fee 5%, TDS 2%)
        cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
        settings = {row['setting_key']: float(row['percentage_value']) for row in cur.fetchall()}
        
        admin_rate = settings.get('admin_fee_percentage', 5.0) / 100
        tds_rate = settings.get('tds_percentage', 2.0) / 100

        # 2. REVENUE & ACTUAL PRODUCT COSTS
        cur.execute("""
            SELECT 
                COALESCE(SUM(up.amount::numeric), 0) AS total_rev,
                COALESCE(SUM(sp.product_cost::numeric), 0) AS total_cost
            FROM user_packages up
            JOIN subscription_plans sp ON up.package_id = sp.id
        """)
        sales_data = cur.fetchone()
        revenue = float(sales_data["total_rev"])
        product_costs = float(sales_data["total_cost"])
        report["total_revenue"] = revenue

        # 3. COMMISSIONS
        cur.execute("SELECT COALESCE(SUM(amount::numeric), 0) AS val FROM commissions")
        commissions = float(cur.fetchone()["val"])

        # 4. GROSS PROFIT
        report["gross_profit"] = revenue - (product_costs + commissions)

        # 5. ADMIN FEES & TDS
        cur.execute("""
            SELECT COALESCE(SUM(amount::numeric), 0) AS total_payouts
            FROM withdraw_requests WHERE LOWER(status) = 'approved'
        """)
        payout_vol = float(cur.fetchone()["total_payouts"])
        
        report["admin_fees"] = payout_vol * admin_rate
        report["total_tds"] = payout_vol * tds_rate

        # 6. NET PROFIT
        report["net_profit"] = report["gross_profit"] + report["admin_fees"]

        # 7. SYSTEM LIABILITY
        cur.execute("SELECT COALESCE(SUM(amount::numeric), 0) AS val FROM wallet_ledger")
        report["total_wallet_liability"] = float(cur.fetchone()["val"])

    return report
