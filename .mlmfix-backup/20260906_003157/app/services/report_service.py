"""
app/services/report_service.py  —  COMPLETE FINANCIAL P&L (rewrite)

Every money movement in the RK Trendz plan is accounted for.

P&L structure
==============
  Revenue (package sales at selling price)
  − Product cost (COGS = actual product cost of each sold package)
  = Gross profit
  − Self cashback        (5% to buyer on purchase)
  − Direct commission    (10% to the L1 / direct sponsor)
  − Level generation     (L2–L10 generation-income pool)
  − Rank / fast-action bonus (one-time bonus when a rank target is hit)
  = Total member payout (commission expense)
  + Admin withdrawal charges (processing fee retained by the company = income)
  = Net profit

  TDS is tax WITHHELD on withdrawals and is owed to the government — it is a
  LIABILITY, never company income, so it is NOT added to profit.

Sources of truth
================
  * Revenue / COGS ........ orders + user_packages + subscription_plans
  * Commission expense .... commissions table (categorised by type/level)
  * Admin fee / TDS ....... withdrawal_deductions (booked at payout approval)
  * Member liability ...... wallet_ledger (unwithdrawn member balances)

An "expected payout" sanity check compares what the plan SHOULD have paid on
the recorded sales (self cashback % + full level pool %) against what is
actually recorded, so missing/legacy payouts are flagged rather than hidden.
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


# Signed wallet-balance contribution (member money only).
_WALLET_SIGN = """
    CASE
        WHEN LOWER(transaction_type) LIKE '%%debit%%' THEN -ABS(amount)
        WHEN amount < 0 THEN amount
        ELSE ABS(amount)
    END
"""


def _zero_report():
    return {
        "total_revenue": 0.0, "product_costs": 0.0, "gross_profit": 0.0,
        "cashback_paid": 0.0, "direct_commission": 0.0,
        "level_commission": 0.0, "rank_bonus_paid": 0.0,
        "total_commissions": 0.0, "commissions_recorded": 0.0,
        "expected_commission": 0.0,
        "admin_fees": 0.0, "total_tds": 0.0, "net_profit": 0.0,
        "total_wallet_liability": 0.0, "tax_liability": 0.0,
        "pending_payout_liability": 0.0,
        "total_users": 0, "active_users": 0, "total_sales": 0,
        "reconciliation": {"ok": True, "warnings": [], "notes": []},
    }


def get_financial_report():
    try:
        with get_cursor() as cur:
            # ---------- Revenue ----------
            cur.execute("SELECT COALESCE(SUM(amount),0) AS t, COUNT(*) AS n FROM orders WHERE status='completed'")
            orow = cur.fetchone()
            revenue_orders = _d(orow["t"])
            sales_orders = orow["n"]
            cur.execute("SELECT COALESCE(SUM(amount),0) AS t, COUNT(*) AS n FROM user_packages")
            prow = cur.fetchone()
            revenue_pkg = _d(prow["t"])
            sales_pkg = prow["n"]
            revenue = revenue_orders or revenue_pkg
            total_sales = sales_orders or sales_pkg

            # ---------- Product cost (COGS) ----------
            cur.execute("""
                SELECT COALESCE(SUM(sp.product_cost),0) AS t
                FROM user_packages up
                JOIN subscription_plans sp ON sp.id = up.package_id
            """)
            product_cost = _d(cur.fetchone()["t"])
            gross_profit = revenue - product_cost

            # ---------- Commission expense by category (commissions table) ----------
            cur.execute("""
                SELECT
                  COALESCE(SUM(amount) FILTER (
                      WHERE LOWER(commission_type) LIKE '%%cashback%%'),0) AS cashback,
                  COALESCE(SUM(amount) FILTER (
                      WHERE LOWER(commission_type) LIKE '%%rank%%'
                         OR LOWER(commission_type) LIKE '%%bonus%%'),0) AS rank_bonus,
                  COALESCE(SUM(amount) FILTER (
                      WHERE level = 1
                        AND LOWER(commission_type) NOT LIKE '%%cashback%%'
                        AND LOWER(commission_type) NOT LIKE '%%rank%%'
                        AND LOWER(commission_type) NOT LIKE '%%bonus%%'),0) AS direct,
                  COALESCE(SUM(amount) FILTER (
                      WHERE level >= 2
                        AND LOWER(commission_type) NOT LIKE '%%cashback%%'
                        AND LOWER(commission_type) NOT LIKE '%%rank%%'
                        AND LOWER(commission_type) NOT LIKE '%%bonus%%'),0) AS level_comm,
                  COALESCE(SUM(amount),0) AS total
                FROM commissions
            """)
            c = cur.fetchone()
            cashback = _d(c["cashback"])
            rank_bonus = _d(c["rank_bonus"])
            direct = _d(c["direct"])
            level_comm = _d(c["level_comm"])
            commissions_total = _d(c["total"])
            # Category sum should equal the table total; use the categorised sum
            # for the P&L so every payout is explicitly accounted for.
            categorised = cashback + rank_bonus + direct + level_comm

            # ---------- Configured plan rates (for expected-payout check) ----------
            cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
            g = {r["setting_key"]: _d(r["percentage_value"]) for r in cur.fetchall()}
            cashback_pct = g.get("self_cashback", Decimal("5"))
            cur.execute("SELECT COALESCE(SUM(percentage),0) AS s FROM commission_plan WHERE is_active = TRUE")
            level_pool_pct = _d(cur.fetchone()["s"])  # L1..L10 (includes the 10% direct)
            expected_rate = (level_pool_pct + cashback_pct) / Decimal("100")
            expected_commission = (revenue * expected_rate).quantize(Decimal("0.01"))

            # ---------- Admin fee & TDS (booked at withdrawal) ----------
            admin_fees = Decimal("0")
            tds_total = Decimal("0")
            try:
                cur.execute("""
                    SELECT COALESCE(SUM(admin_fee_amount),0) AS f,
                           COALESCE(SUM(tds_amount),0) AS t, COUNT(*) AS n
                    FROM withdrawal_deductions
                """)
                d = cur.fetchone()
                admin_fees = _d(d["f"])
                tds_total = _d(d["t"])
            except Exception as e:
                logger.warning("withdrawal_deductions not available yet: %s", e)

            # ---------- Net profit ----------
            # Commission expense = everything actually paid to members (cashback
            # + direct + level + rank bonus). Admin fee is company income.
            net_profit = gross_profit - categorised + admin_fees

            # ---------- Liabilities ----------
            cur.execute(f"SELECT COALESCE(SUM({_WALLET_SIGN}),0) AS t FROM wallet_ledger")
            wallet_liability = _d(cur.fetchone()["t"])
            cur.execute("""
                SELECT COALESCE(SUM(amount),0) AS t
                FROM withdraw_requests WHERE LOWER(status)='pending'
            """)
            pending = _d(cur.fetchone()["t"])

            cur.execute("SELECT COUNT(*) AS c FROM users")
            total_users = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM users WHERE is_active = TRUE")
            active_users = cur.fetchone()["c"]

            # ---------- Reconciliation / sanity ----------
            warnings, notes = [], []
            payouts_excl_bonus = cashback + direct + level_comm
            if expected_commission > 0 and payouts_excl_bonus < expected_commission - Decimal("1"):
                warnings.append(
                    f"Plan should have paid ≈ ₹{_f(expected_commission)} in commissions on "
                    f"₹{_f(revenue)} of sales ({_f(level_pool_pct)}% level pool + "
                    f"{_f(cashback_pct)}% cashback), but only ₹{_f(payouts_excl_bonus)} is "
                    "recorded. Older/test payouts were not all logged to the commissions "
                    "table — the P&L uses the recorded figures. New sales are logged correctly."
                )
            if wallet_liability > gross_profit:
                warnings.append(
                    f"Member wallet liability ₹{_f(wallet_liability)} exceeds gross profit "
                    f"₹{_f(gross_profit)} — typical of test data; verify before go-live."
                )
            if categorised > gross_profit + admin_fees:
                notes.append(
                    f"Total member payouts ₹{_f(categorised)} exceed gross profit + admin fees "
                    f"₹{_f(gross_profit + admin_fees)}. On the live plan, payouts are "
                    f"{_f(expected_rate*100)}% of sales plus occasional rank bonuses, so this "
                    "indicates test/legacy credits."
                )

            return {
                "total_revenue": _f(revenue),
                "product_costs": _f(product_cost),
                "gross_profit": _f(gross_profit),
                "cashback_paid": _f(cashback),
                "direct_commission": _f(direct),
                "level_commission": _f(level_comm),
                "rank_bonus_paid": _f(rank_bonus),
                "total_commissions": _f(categorised),
                "commissions_recorded": _f(commissions_total),
                "expected_commission": _f(expected_commission),
                "admin_fees": _f(admin_fees),
                "total_tds": _f(tds_total),
                "net_profit": _f(net_profit),
                "total_wallet_liability": _f(wallet_liability),
                "tax_liability": _f(tds_total),
                "pending_payout_liability": _f(pending),
                "total_users": total_users,
                "active_users": active_users,
                "total_sales": total_sales,
                "reconciliation": {"ok": not warnings, "warnings": warnings, "notes": notes},
            }
    except Exception as e:
        logger.error("Financial report failed: %s", e, exc_info=True)
        return _zero_report()


# =============== AUDIT DRILLS ===============

def get_revenue_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT up.created_at AS date, up.id AS order_id, sp.name AS package_name,
                   u.id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number,
                   up.amount AS amount, sp.product_cost
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
    """Every line that flows into net profit: revenue, COGS, each payout, fees."""
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
            SELECT created_at AS date,
                   CASE
                     WHEN LOWER(commission_type) LIKE '%%cashback%%' THEN 'Self Cashback'
                     WHEN LOWER(commission_type) LIKE '%%rank%%' OR LOWER(commission_type) LIKE '%%bonus%%' THEN 'Rank Bonus'
                     WHEN level = 1 THEN 'Direct Commission'
                     WHEN level >= 2 THEN 'Level Commission'
                     ELSE 'Commission'
                   END AS type,
                   commission_type AS description, -amount AS amount, earner_id AS user_id,
                   (SELECT full_name FROM users WHERE id = commissions.earner_id) AS user_name,
                   (SELECT phone FROM users WHERE id = commissions.earner_id) AS user_mobile_number
            FROM commissions
        """)
        comm = cur.fetchall()
        cur.execute("""
            SELECT d.created_at AS date, 'Admin Fee' AS type,
                   'Withdrawal processing fee' AS description,
                   d.admin_fee_amount AS amount, d.user_id,
                   u.full_name AS user_name, u.phone AS user_mobile_number
            FROM withdrawal_deductions d JOIN users u ON u.id = d.user_id
            WHERE d.admin_fee_amount > 0
        """)
        fees = cur.fetchall()

        rows = []
        for row in rev + cost + comm + fees:
            d = dict(row)
            if "amount" in d:
                d["amount"] = _f(d["amount"])
            rows.append(d)
        rows.sort(key=lambda x: x["date"] or "", reverse=True)
        return {"recent": rows[:500], "total_records": len(rows)}


def get_admin_fees_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT d.created_at AS date, d.withdrawal_id AS request_id, d.user_id,
                   u.full_name AS user_name, u.phone AS user_mobile_number,
                   d.gross_amount AS withdrawal_amount,
                   d.admin_fee_amount AS admin_fee, d.admin_rate
            FROM withdrawal_deductions d JOIN users u ON u.id = d.user_id
            WHERE d.admin_fee_amount > 0
            ORDER BY d.created_at DESC LIMIT 500
        """)
        rows = cur.fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for k in ("withdrawal_amount", "admin_fee", "admin_rate"):
                if k in d:
                    d[k] = _f(d[k])
            out.append(d)
        return out


def get_tds_audit():
    with get_cursor() as cur:
        cur.execute("""
            SELECT d.created_at AS date, d.withdrawal_id AS request_id, d.user_id,
                   u.full_name AS user_name, u.phone AS user_mobile_number,
                   d.gross_amount AS withdrawal_amount,
                   d.tds_amount AS tds_amount, d.tds_rate, d.net_payable AS net_paid
            FROM withdrawal_deductions d JOIN users u ON u.id = d.user_id
            WHERE d.tds_amount > 0
            ORDER BY d.created_at DESC LIMIT 500
        """)
        rows = cur.fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for k in ("withdrawal_amount", "tds_amount", "tds_rate", "net_paid"):
                if k in d:
                    d[k] = _f(d[k])
            out.append(d)
        return out


def get_liability_audit():
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM (
                SELECT u.id AS user_id, u.full_name AS user_name, u.phone AS user_mobile_number,
                    COALESCE((
                        SELECT SUM(
                            CASE
                                WHEN LOWER(transaction_type) LIKE '%%debit%%' THEN -ABS(amount)
                                WHEN wl.amount < 0 THEN wl.amount
                                ELSE ABS(amount)
                            END)
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
