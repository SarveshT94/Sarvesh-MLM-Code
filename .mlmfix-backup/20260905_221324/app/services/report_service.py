"""
app/services/report_service.py  —  REWRITE (drop-in replacement)

Financial reporting for the admin dashboard. Principles (per the business
spec): all figures are derived from the controlled ledger / transactional
records (source of truth), money is treated as Decimal internally, and the
report reconciles and WARNS instead of presenting an over-confident profit.

P&L (accrual)
  Revenue            = sum of package sales (orders/user_packages)
  - Product cost     = sum of product_cost per sold package   (COGS)
  = Gross profit
  - Commission expense = sum of commissions actually posted
  + Admin fee income  = admin fees withheld on approved withdrawals
  = Net profit

TDS is NOT income — it is tax withheld that the company owes the government,
so it appears on the liability side, never in profit.

Balance / liability
  User wallet liability = sum of unwithdrawn member wallet balances
  Tax liability (TDS)   = TDS withheld on approved withdrawals
  Pending payouts       = withdrawal requests not yet processed
                          (these points are still inside wallet balances, so
                          they are reported as a memo, not double-counted)

A reconciliation block flags the dangerous condition where the money credited
to member wallets does not match the commissions table, or where member
liability exceeds collected gross profit.
"""
from decimal import Decimal

from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def _d(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0))
    except Exception:
        return Decimal("0")


def _f(value) -> float:
    return float(_d(value).quantize(Decimal("0.01")))


# Wallet balance sign convention (must match wallet_service):
# transaction types containing 'debit' reduce the balance; everything else
# adds it. p2p_transfer_out stores a negative amount but historically lacked
# the 'debit' keyword, so we ALSO treat any stored negative amount as negative.
_WALLET_SUM = """
    SELECT COALESCE(SUM(
        CASE
            WHEN LOWER(transaction_type) LIKE '%%debit%%' THEN -ABS(amount)
            WHEN amount < 0 THEN amount
            ELSE ABS(amount)
        END
    ), 0) AS bal
    FROM wallet_ledger
"""


def get_financial_report():
    default = {
        "total_revenue": 0.0, "product_costs": 0.0, "gross_profit": 0.0,
        "total_commissions": 0.0, "admin_fees": 0.0, "total_tds": 0.0,
        "net_profit": 0.0, "total_wallet_liability": 0.0,
        "pending_payout_liability": 0.0,
        "total_users": 0, "active_users": 0,
        "reconciliation": {"ok": True, "warnings": []},
    }
    try:
        with get_cursor() as cur:
            cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
            rates = {r["setting_key"]: _d(r["percentage_value"]) for r in cur.fetchall()}
            admin_rate = rates.get("admin_fee_percentage", Decimal("10")) / Decimal("100")
            tds_rate = rates.get("tds_percentage", Decimal("10")) / Decimal("100")

            # ---- Revenue (prefer orders; fall back to user_packages) ----
            cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM orders WHERE status='completed'")
            revenue = _d(cur.fetchone()["t"])
            cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM user_packages")
            revenue_pkg = _d(cur.fetchone()["t"])
            revenue = revenue or revenue_pkg

            # ---- Product cost (COGS) ----
            cur.execute("""
                SELECT COALESCE(SUM(sp.product_cost), 0) AS t
                FROM user_packages up
                JOIN subscription_plans sp ON sp.id = up.package_id
            """)
            product_cost = _d(cur.fetchone()["t"])
            gross_profit = revenue - product_cost

            # ---- Commission expense (money posted as commission) ----
            cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM commissions")
            commissions = _d(cur.fetchone()["t"])

            # ---- Withdrawals drive the withheld TDS / admin fees ----
            cur.execute("""
                SELECT COALESCE(SUM(amount),0) AS t
                FROM withdraw_requests WHERE LOWER(status)='approved'
            """)
            approved_payout = _d(cur.fetchone()["t"])
            admin_fees = (approved_payout * admin_rate).quantize(Decimal("0.01"))
            tds_total = (approved_payout * tds_rate).quantize(Decimal("0.01"))

            cur.execute("""
                SELECT COALESCE(SUM(amount),0) AS t
                FROM withdraw_requests WHERE LOWER(status)='pending'
            """)
            pending = _d(cur.fetchone()["t"])

            # ---- Net profit (TDS never added: it is owed to government) ----
            net_profit = gross_profit - commissions + admin_fees

            # ---- Liabilities ----
            cur.execute(_WALLET_SUM)
            wallet_liability = _d(cur.fetchone()["bal"])

            cur.execute("SELECT COUNT(*) AS c FROM users")
            total_users = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM users WHERE is_active = TRUE")
            active_users = cur.fetchone()["c"]

            # ---- Reconciliation / health checks ----
            warnings = []
            # Money credited into wallets that is NOT explained by commissions.
            cur.execute("""
                SELECT COALESCE(SUM(
                    CASE WHEN LOWER(transaction_type) LIKE '%%debit%%' THEN -ABS(amount)
                         WHEN amount < 0 THEN amount
                         ELSE ABS(amount) END), 0) AS t
                FROM wallet_ledger
                WHERE LOWER(transaction_type) NOT LIKE '%%withdraw%%'
            """)
            non_withdrawal_wallet = _d(cur.fetchone()["t"])
            if non_withdrawal_wallet - commissions > Decimal("1.00"):
                warnings.append(
                    f"Wallet credits (₹{_f(non_withdrawal_wallet)}) exceed recorded "
                    f"commissions (₹{_f(commissions)}) by ₹{_f(non_withdrawal_wallet - commissions)}. "
                    "Some wallet credits have no matching commission record (manual/test "
                    "credits or transfers)."
                )
            if wallet_liability > gross_profit:
                warnings.append(
                    f"Member wallet liability (₹{_f(wallet_liability)}) exceeds gross profit "
                    f"(₹{_f(gross_profit)}). Verify payouts against real sales before launch."
                )
            if commissions > gross_profit:
                warnings.append(
                    f"Commission expense (₹{_f(commissions)}) exceeds gross profit "
                    f"(₹{_f(gross_profit)}) — plan is paying out more than it earns."
                )

            return {
                "total_revenue": _f(revenue),
                "product_costs": _f(product_cost),
                "gross_profit": _f(gross_profit),
                "total_commissions": _f(commissions),
                "admin_fees": _f(admin_fees),
                "total_tds": _f(tds_total),
                "net_profit": _f(net_profit),
                "total_wallet_liability": _f(wallet_liability),
                "tax_liability": _f(tds_total),
                "pending_payout_liability": _f(pending),
                "total_users": total_users,
                "active_users": active_users,
                "reconciliation": {"ok": not warnings, "warnings": warnings},
            }
    except Exception as e:
        logger.error("Financial report failed: %s", e, exc_info=True)
        return default


# =============== AUDIT DRILLS (unchanged shapes, ledger based) ===============

def get_revenue_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT up.created_at AS date, up.id AS order_id, sp.name AS package_name,
                   u.id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number,
                   up.amount AS amount
            FROM user_packages up
            JOIN users u ON u.id = up.user_id
            JOIN subscription_plans sp ON sp.id = up.package_id
            ORDER BY up.created_at DESC LIMIT 500
        """)
        return cur.fetchall()


def get_gross_profit_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT up.created_at AS date, u.id AS user_id, u.full_name AS user_name,
                   u.phone AS user_mobile_number, sp.name AS plan_name,
                   sp.product_cost AS product_cost, up.amount AS revenue,
                   (up.amount - sp.product_cost) AS gross_profit_contribution
            FROM user_packages up
            JOIN users u ON u.id = up.user_id
            JOIN subscription_plans sp ON sp.id = up.package_id
            ORDER BY up.created_at DESC LIMIT 500
        """)
        rows = cur.fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for k in ("product_cost", "revenue", "gross_profit_contribution"):
                if k in d:
                    d[k] = _f(d[k])
            out.append(d)
        return out


def get_net_profit_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT created_at AS date, 'Revenue' AS type, 'Package purchase' AS description,
                   amount, user_id,
                   (SELECT full_name FROM users WHERE id = user_packages.user_id) AS user_name,
                   (SELECT phone FROM users WHERE id = user_packages.user_id) AS user_mobile_number
            FROM user_packages
        """)
        rev = cur.fetchall()
        cur.execute("""
            SELECT up.created_at AS date, 'Product Cost' AS type, 'Cost of package' AS description,
                   -sp.product_cost AS amount, up.user_id AS user_id,
                   u.full_name AS user_name, u.phone AS user_mobile_number
            FROM user_packages up
            JOIN subscription_plans sp ON sp.id = up.package_id
            JOIN users u ON u.id = up.user_id
        """)
        cost = cur.fetchall()
        cur.execute("""
            SELECT c.created_at AS date, 'Commission' AS type, c.commission_type AS description,
                   -c.amount AS amount, c.earner_id AS user_id,
                   u.full_name AS user_name, u.phone AS user_mobile_number
            FROM commissions c JOIN users u ON u.id = c.earner_id
        """)
        comm = cur.fetchall()
        cur.execute("""
            SELECT wr.processed_at AS date, 'Admin Fee' AS type, 'Withheld from withdrawal' AS description,
                   (wr.amount * gc.percentage_value/100) AS amount, wr.user_id,
                   u.full_name AS user_name, u.phone AS user_mobile_number
            FROM withdraw_requests wr
            JOIN users u ON u.id = wr.user_id
            CROSS JOIN global_commissions gc
            WHERE gc.setting_key='admin_fee_percentage' AND LOWER(wr.status)='approved'
        """)
        admin = cur.fetchall()

        rows = []
        for row in rev + cost + comm + admin:
            d = dict(row)
            if "amount" in d:
                d["amount"] = _f(d["amount"])
            rows.append(d)
        rows.sort(key=lambda x: x["date"] or "", reverse=True)
        return {"recent": rows[:500], "total_records": len(rows)}


def get_admin_fees_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT wr.processed_at AS date, wr.id AS request_id, u.id AS user_id,
                   wr.amount AS withdrawal_amount,
                   wr.amount * (SELECT percentage_value/100 FROM global_commissions
                                WHERE setting_key='admin_fee_percentage') AS admin_fee,
                   u.phone AS user_mobile_number, u.full_name AS user_name
            FROM withdraw_requests wr JOIN users u ON u.id = wr.user_id
            WHERE LOWER(wr.status)='approved'
            ORDER BY wr.processed_at DESC LIMIT 500
        """)
        rows = cur.fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for k in ("withdrawal_amount", "admin_fee"):
                if k in d:
                    d[k] = _f(d[k])
            out.append(d)
        return out


def get_tds_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT wr.processed_at AS date, wr.id AS request_id, u.id AS user_id,
                   wr.amount AS withdrawal_amount,
                   wr.amount * (SELECT percentage_value/100 FROM global_commissions
                                WHERE setting_key='tds_percentage') AS tds_amount,
                   u.phone AS user_mobile_number, u.full_name AS user_name
            FROM withdraw_requests wr JOIN users u ON u.id = wr.user_id
            WHERE LOWER(wr.status)='approved'
            ORDER BY wr.processed_at DESC LIMIT 500
        """)
        rows = cur.fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for k in ("withdrawal_amount", "tds_amount"):
                if k in d:
                    d[k] = _f(d[k])
            out.append(d)
        return out


def get_liability_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM (
                SELECT u.id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number,
                    COALESCE((
                        SELECT SUM(CASE WHEN LOWER(transaction_type) LIKE '%%debit%%' THEN -ABS(amount)
                                        WHEN wl.amount < 0 THEN wl.amount
                                        ELSE ABS(amount) END)
                        FROM wallet_ledger wl WHERE wl.user_id = u.id), 0) AS net_wallet_balance,
                    COALESCE((SELECT SUM(amount) FROM withdraw_requests
                              WHERE user_id = u.id AND LOWER(status)='pending'), 0) AS pending_withdrawals
                FROM users u
            ) t
            WHERE net_wallet_balance > 0
            ORDER BY net_wallet_balance DESC
            LIMIT 500
        """)
        rows = cur.fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for k in ("net_wallet_balance", "pending_withdrawals"):
                if k in d:
                    d[k] = _f(d[k])
            out.append(d)
        return out
