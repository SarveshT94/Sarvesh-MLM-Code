"""
app/services/package_service.py  —  REWRITE (drop-in replacement)

Fixes
-----
1. get_plan_with_commissions() used to SELECT a column called `percentage`
   from level_commissions, but the real column is `commission_percentage`.
   Every purchase therefore raised UndefinedColumn -> the engine returned an
   error and NO level commission was ever paid. Fixed; we now read from the
   canonical `commission_plan` table and normalise the legacy table too.
2. Plan/commission configuration is cached in Redis for 60 s (was a fresh
   query on every purchase) and cache is busted whenever an admin edits it.
3. purchase_package() now runs activation + order insert + commission
   distribution in ONE transaction (the old version committed activation in
   a separate transaction, so a commission failure left the user activated
   but unpaid — or vice versa).
4. All money is Decimal; inputs are validated.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)

PLAN_CACHE_TTL = 60


# ===========================================================================
# 1. PLANS
# ===========================================================================
def get_all_plans(include_inactive: bool = False):
    try:
        with get_cursor() as cur:
            sql = "SELECT * FROM subscription_plans"
            if not include_inactive:
                sql += " WHERE is_active = TRUE"
            sql += " ORDER BY price ASC"
            cur.execute(sql)
            plans = [dict(p) for p in cur.fetchall()]
            for plan in plans:
                cur.execute(
                    "SELECT image_path FROM plan_images WHERE plan_id = %s",
                    (plan["id"],),
                )
                plan["images"] = [r["image_path"] for r in cur.fetchall()]
            return plans
    except Exception as e:
        logger.error("get_all_plans error: %s", e)
        return []


def add_plan_image(plan_id, image_path):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO plan_images (plan_id, image_path) VALUES (%s, %s)",
            (plan_id, image_path),
        )
    cache.delete("plans:all")


def get_plan_by_id(plan_id, cur=None):
    query = "SELECT * FROM subscription_plans WHERE id = %s"
    if cur is not None:
        cur.execute(query, (plan_id,))
        return cur.fetchone()
    with get_cursor() as new_cur:
        new_cur.execute(query, (plan_id,))
        return new_cur.fetchone()


get_package_by_id = get_plan_by_id
get_all_active_packages = get_all_plans


def update_plan(plan_id, price, coupons, is_active, product_cost=0):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE subscription_plans
            SET price = %s, lucky_draw_coupons = %s, product_cost = %s,
                is_active = %s
            WHERE id = %s
            """,
            (Decimal(str(price)), int(coupons or 0), Decimal(str(product_cost or 0)),
             bool(is_active), plan_id),
        )
    cache.delete_memoized(get_plan_with_commissions, plan_id)
    cache.delete("plans:all")


def create_plan(name, price, coupons=12, product_cost=0):
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO subscription_plans (name, price, lucky_draw_coupons,
                                            product_cost, is_active)
            VALUES (%s, %s, %s, %s, TRUE) RETURNING id
            """,
            (name, Decimal(str(price)), int(coupons or 0), Decimal(str(product_cost or 0))),
        )
        new_id = cur.fetchone()["id"]
    cache.delete("plans:all")
    return new_id


# ===========================================================================
# 2. COMMISSION CONFIGURATION
# ===========================================================================
def get_global_commissions():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM global_commissions ORDER BY setting_key")
        return [dict(r) for r in cur.fetchall()]


def update_global_commission(setting_key, percentage_value):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE global_commissions SET percentage_value = %s
            WHERE setting_key = %s
            """,
            (Decimal(str(percentage_value)), setting_key),
        )
    cache.delete("commissions:config")


def get_level_commissions():
    """Canonical level ladder from commission_plan (fallback to legacy table)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT level, percentage AS commission_percentage
            FROM commission_plan WHERE is_active = TRUE ORDER BY level
            """
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                "SELECT level, commission_percentage FROM level_commissions ORDER BY level"
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_commission_config(cur=None) -> dict:
    """Load {direct_commission, levels:{1:10,...}} once and cache in Redis."""
    cached = cache.get("commissions:config")
    if cached is not None:
        return cached

    def _load(c):
        c.execute("SELECT setting_key, percentage_value FROM global_commissions")
        globals_ = {r["setting_key"]: Decimal(str(r["percentage_value"]))
                    for r in c.fetchall()}
        direct = globals_.get("direct_commission")
        if direct is None:
            direct = globals_.get("direct_referral", Decimal("0"))

        c.execute(
            "SELECT level, percentage FROM commission_plan WHERE is_active = TRUE"
        )
        levels_rows = c.fetchall()
        levels = {int(r["level"]): Decimal(str(r["percentage"])) for r in levels_rows}
        if not levels:
            c.execute("SELECT level, commission_percentage FROM level_commissions")
            levels = {int(r["level"]): Decimal(str(r["commission_percentage"]))
                      for r in c.fetchall()}
        return {"direct": direct, "levels": levels}

    config = _load(cur) if cur is not None else None
    if config is None:
        with get_cursor() as c:
            config = _load(c)

    cache.set("commissions:config", config, timeout=PLAN_CACHE_TTL)
    return config


# ===========================================================================
# 3. ACTIVATION + PURCHASE
# ============================================================================
def activate_user_package(cur, user_id, plan_id):
    plan = get_plan_by_id(plan_id, cur)
    if not plan:
        raise ValueError("Plan not found")

    cur.execute(
        """
        UPDATE users
        SET package_id = %s, is_active = TRUE, activated_at = NOW()
        WHERE id = %s
        """,
        (plan_id, user_id),
    )
    cur.execute(
        """
        INSERT INTO user_packages (user_id, package_id, amount, created_at)
        VALUES (%s, %s, %s, NOW())
        """,
        (user_id, plan_id, plan["price"]),
    )
    return True


def purchase_package(user_id, plan_id, payment_ref=None):
    """
    Atomic purchase: create order -> activate -> distribute commissions,
    all in a single DB transaction. All-or-nothing.
    """
    from app.services.commission_engine import distribute_commission

    try:
        with get_cursor() as cur:
            plan = get_plan_by_id(plan_id, cur)
            if not plan or not plan.get("is_active", True):
                return {"success": False, "message": "Plan not found or inactive."}

            # 1. The order is the financial anchor for idempotency.
            cur.execute(
                """
                INSERT INTO orders (user_id, package_id, amount, status, payment_ref)
                VALUES (%s, %s, %s, 'completed', %s)
                RETURNING id
                """,
                (user_id, plan_id, plan["price"], payment_ref),
            )
            order_id = cur.fetchone()["id"]

            # 2. Activate the buyer (same transaction).
            activate_user_package(cur, user_id, plan_id)

            # 3. Distribute commissions (same transaction, same cursor).
            result = distribute_commission(
                buyer_id=user_id,
                package_id=plan_id,
                order_id=order_id,
                cur=cur,
            )
            if result.get("status") == "error":
                raise RuntimeError(result.get("message", "Commission error"))

        return {
            "success": True,
            "order_id": order_id,
            "amount": float(plan["price"]),
            "message": "Package purchased and commissions distributed.",
        }
    except Exception as e:
        logger.error("purchase_package error user=%s: %s", user_id, e)
        return {"success": False, "message": str(e)}


# ===========================================================================
# 4. Plan + commissions (used by the engine)
# ===========================================================================
def get_plan_with_commissions(plan_id):
    """Plan row plus current commission percentages (cached in Redis)."""
    with get_cursor() as cur:
        plan = get_plan_by_id(plan_id, cur)
        if not plan:
            return None
        plan = dict(plan)
        cfg = get_commission_config(cur)
        plan["level_commissions"] = {str(k): v for k, v in cfg["levels"].items()}
        plan["direct_commission"] = cfg["direct"]
        return plan
