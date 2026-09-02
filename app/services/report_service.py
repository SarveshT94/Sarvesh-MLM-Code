"""
app/services/report_service.py
"""

from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)

def safe_float(val):
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def get_financial_report():
    default = {
        'total_revenue': 0.0, 'product_costs': 0.0, 'gross_profit': 0.0,
        'total_commissions': 0.0, 'admin_fees': 0.0, 'total_tds': 0.0,
        'net_profit': 0.0, 'total_wallet_liability': 0.0, 'pending_payout_liability': 0.0,
        'total_users': 0, 'active_users': 0,
    }
    try:
        with get_cursor() as cur:
            cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
            rates = {row['setting_key']: safe_float(row['percentage_value']) for row in cur.fetchall()}
            admin_rate = rates.get('admin_fee_percentage', 5.0) / 100.0
            tds_rate   = rates.get('tds_percentage', 2.0) / 100.0

            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM user_packages")
            revenue = safe_float(cur.fetchone()['total'])

            cur.execute("""
                SELECT COALESCE(SUM(sp.product_cost), 0) AS total
                FROM user_packages up
                JOIN subscription_plans sp ON up.package_id = sp.id
            """)
            product_cost = safe_float(cur.fetchone()['total'])

            gross_profit = revenue - product_cost

            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM commissions")
            commissions = safe_float(cur.fetchone()['total'])

            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM withdraw_requests WHERE LOWER(status) = 'approved'")
            payout_vol = safe_float(cur.fetchone()['total'])

            admin_fees = payout_vol * admin_rate
            tds_total  = payout_vol * tds_rate

            net_profit = gross_profit - commissions + admin_fees

            # THE FIX: Bulletproof Wallet Calculation
            cur.execute("""
                SELECT COALESCE(SUM(
                    CASE 
                        WHEN LOWER(transaction_type) LIKE '%debit%' THEN -ABS(amount)
                        ELSE ABS(amount)
                    END
                ), 0) AS net
                FROM wallet_ledger
            """)
            net_wallet = safe_float(cur.fetchone()['net'])

            cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM withdraw_requests WHERE LOWER(status) = 'pending'")
            pending = safe_float(cur.fetchone()['total'])

            # Liability correctly factors the true unwithdrawn wallet balance
            liability = net_wallet + tds_total

            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            total_users = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_active = TRUE")
            active_users = cur.fetchone()['cnt']

            return {
                'total_revenue': round(revenue, 2),
                'product_costs': round(product_cost, 2),
                'gross_profit': round(gross_profit, 2),
                'total_commissions': round(commissions, 2),
                'admin_fees': round(admin_fees, 2),
                'total_tds': round(tds_total, 2),
                'net_profit': round(net_profit, 2),
                'total_wallet_liability': round(liability, 2),
                'pending_payout_liability': round(pending, 2),
                'total_users': total_users,
                'active_users': active_users,
            }
    except Exception as e:
        logger.error(f"Financial report failed: {e}", exc_info=True)
        return default


# =============== AUDIT DRILLS ===============

def get_revenue_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT up.created_at AS date, up.id AS order_id, sp.name AS package_name,
                   u.id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number, up.amount AS amount
            FROM user_packages up
            JOIN users u ON u.id = up.user_id
            JOIN subscription_plans sp ON sp.id = up.package_id
            ORDER BY up.created_at DESC LIMIT 500
        """)
        return cur.fetchall()

def get_gross_profit_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT up.created_at AS date, u.id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number,
                   sp.name AS plan_name, sp.product_cost AS product_cost, up.amount AS revenue,
                   (up.amount - sp.product_cost) AS gross_profit_contribution
            FROM user_packages up
            JOIN users u ON u.id = up.user_id
            JOIN subscription_plans sp ON sp.id = up.package_id
            ORDER BY up.created_at DESC LIMIT 500
        """)
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for k in ('product_cost', 'revenue', 'gross_profit_contribution'):
                if k in d: d[k] = float(d[k]) if d[k] is not None else 0.0
            result.append(d)
        return result

def get_net_profit_audit():
    with get_cursor() as cur:
        cur.execute("SELECT created_at AS date, 'Revenue' AS type, 'Package purchase' AS description, amount, user_id, (SELECT full_name FROM users WHERE id = user_id) AS user_name, (SELECT phone FROM users WHERE id = user_id) AS user_mobile_number FROM user_packages")
        rev = cur.fetchall()
        
        cur.execute("SELECT up.created_at AS date, 'Product Cost' AS type, 'Cost of package' AS description, -sp.product_cost AS amount, up.user_id, u.full_name AS user_name, u.phone AS user_mobile_number FROM user_packages up JOIN subscription_plans sp ON sp.id = up.package_id JOIN users u ON u.id = up.user_id")
        cost = cur.fetchall()
        
        cur.execute("SELECT c.created_at AS date, 'Commission' AS type, c.commission_type AS description, -c.amount AS amount, c.earner_id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number FROM commissions c JOIN users u ON u.id = c.earner_id")
        comm = cur.fetchall()
        
        cur.execute("SELECT wr.processed_at AS date, 'Admin Fee' AS type, 'Deducted from withdrawal' AS description, (wr.amount * (SELECT percentage_value/100 FROM global_commissions WHERE setting_key='admin_fee_percentage')) AS amount, wr.user_id, u.full_name AS user_name, u.phone AS user_mobile_number FROM withdraw_requests wr JOIN users u ON u.id = wr.user_id WHERE LOWER(wr.status) = 'approved'")
        admin = cur.fetchall()
        
        all_rows = []
        for row in rev + cost + comm + admin:
            d = dict(row)
            if 'amount' in d: d['amount'] = float(d['amount']) if d['amount'] is not None else 0.0
            all_rows.append(d)
        all_rows.sort(key=lambda x: x['date'], reverse=True)
        return {'recent': all_rows[:500], 'total_records': len(all_rows)}

def get_admin_fees_audit():
    with get_cursor() as cur:
        cur.execute("SELECT wr.processed_at AS date, wr.id AS request_id, u.id AS user_id, wr.amount AS withdrawal_amount, wr.amount * (SELECT percentage_value/100 FROM global_commissions WHERE setting_key='admin_fee_percentage') AS admin_fee, u.phone AS user_mobile_number, u.full_name AS user_name FROM withdraw_requests wr JOIN users u ON u.id = wr.user_id WHERE LOWER(wr.status) = 'approved' ORDER BY wr.processed_at DESC LIMIT 500")
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for k in ('withdrawal_amount', 'admin_fee'):
                if k in d: d[k] = float(d[k]) if d[k] is not None else 0.0
            result.append(d)
        return result

def get_tds_audit():
    with get_cursor() as cur:
        cur.execute("SELECT wr.processed_at AS date, wr.id AS request_id, u.id AS user_id, wr.amount AS withdrawal_amount, wr.amount * (SELECT percentage_value/100 FROM global_commissions WHERE setting_key='tds_percentage') AS tds_amount, u.phone AS user_mobile_number, u.full_name AS user_name FROM withdraw_requests wr JOIN users u ON u.id = wr.user_id WHERE LOWER(wr.status) = 'approved' ORDER BY wr.processed_at DESC LIMIT 500")
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for k in ('withdrawal_amount', 'tds_amount'):
                if k in d: d[k] = float(d[k]) if d[k] is not None else 0.0
            result.append(d)
        return result

def get_liability_audit():
    with get_cursor() as cur:
        # THE FIX: Bulletproof Drilldown
        cur.execute("""
            SELECT * FROM (
                SELECT u.id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number,
                    COALESCE((SELECT SUM(CASE WHEN LOWER(transaction_type) LIKE '%debit%' THEN -ABS(amount) ELSE ABS(amount) END) 
                              FROM wallet_ledger WHERE user_id = u.id), 0) AS net_wallet_balance,
                    COALESCE((SELECT SUM(amount) FROM withdraw_requests WHERE user_id = u.id AND LOWER(status) = 'pending'), 0) AS pending_withdrawals,
                    COALESCE((SELECT SUM(amount) * (SELECT percentage_value/100 FROM global_commissions WHERE setting_key='tds_percentage')
                              FROM withdraw_requests WHERE user_id = u.id AND LOWER(status) = 'approved'), 0) AS tds_contribution
                FROM users u
            ) t
            WHERE net_wallet_balance + tds_contribution > 0
            ORDER BY net_wallet_balance + tds_contribution DESC
            LIMIT 500
        """)
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for k in ('net_wallet_balance', 'pending_withdrawals', 'tds_contribution'):
                if k in d: d[k] = float(d[k]) if d[k] is not None else 0.0
            result.append(d)
        return result
