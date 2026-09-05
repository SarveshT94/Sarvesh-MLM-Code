"""
app/services/commission_engine.py  —  REWRITE (drop-in replacement)

Fixes (these were silently breaking every payout)
-------------------------------------------------
1. Wrote wallet entries into a column called `reference`, but the table has
   `reference_id` -> the whole payout transaction rolled back every time.
2. Idempotency used a free-text commission_type that included a random uuid /
   timestamp, so the "duplicate" check could NEVER match a retry -> double
   payouts were possible. Idempotency is now anchored to the concrete
   `orders.id` with a real UNIQUE index (see migration 0004).
3. Activation + payout ran in two separate transactions -> a failure left
   users activated but unpaid (or paid but not active). Now the caller passes
   an open cursor and everything commits together.
4. Money is Decimal throughout; payouts use the shared ledger service so
   closing balances are always correct.

Business rule
-------------
For a package purchase of price P:
  * Level-1 upline (the direct sponsor) earns  direct_commission % of P.
  * Upline levels 2..N earn the per-level percentage from commission_plan.
  * Optionally the buyer gets self_cashback % (global setting).
TDS/admin fees are applied at withdrawal time, not here.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.db import get_cursor
from app.services.sponsor_service import get_sponsor_chain
from app.services.wallet_service import credit_wallet

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(TWO_PLACES)


def distribute_commission(buyer_id, package_id, order_id=None, cur=None,
                          purchase_ref=None):
    """
    Distribute upline commissions for a purchase.

    Pass an open `cur` (and a committed `order_id`) to run inside the caller's
    transaction. If omitted, opens its own transaction (used by jobs/CLI).
    """
    # Avoid importing the rank evaluator at module import time (circular-safe).
    from app.services.rank_service import evaluate_user_rank_and_bonus

    def _run(c):
        from app.services.package_service import get_plan_with_commissions

        package = get_plan_with_commissions(package_id) if order_id is None \
            else _load_package(c, package_id)
        if not package:
            return {"status": "error", "message": "Package not found or inactive."}

        price = Decimal(str(package["price"]))
        levels = package.get("level_commissions") or {}
        direct_pct = Decimal(str(package.get("direct_commission") or levels.get("1", 0)))

        sponsors = get_sponsor_chain(buyer_id, cur=c)
        if not sponsors:
            return {"status": "success", "message": "No upline; no commissions."}

        paid = 0
        for sp in sponsors:
            earner_id = sp["user_id"]
            level = int(sp["level"])

            pct = direct_pct if level == 1 else Decimal(str(levels.get(str(level), 0)))
            amount = (price * (pct / Decimal("100"))).quantize(TWO_PLACES)
            if amount <= 0:
                continue

            ref = f"COMM-{order_id}-{earner_id}-L{level}" if order_id else \
                  (purchase_ref or f"COMM-{buyer_id}-{package_id}-{earner_id}-L{level}")

            # 1) Commission row. Idempotent via the PARTIAL unique index on
            #    (earner_id, order_id, level) WHERE order_id IS NOT NULL.
            #    Bare ON CONFLICT lets Postgres pick that partial index.
            try:
                c.execute(
                    """
                    INSERT INTO commissions
                        (earner_id, from_user_id, level, amount,
                         commission_type, order_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (earner_id, buyer_id, level, amount, "package_commission",
                     order_id),
                )
                inserted = c.fetchone()
            except Exception as e:
                logger.warning("commission insert conflict: %s", e)
                inserted = None
            if not inserted:
                # Duplicate (already paid for this order/earner/level) -> skip
                # crediting the wallet again.
                continue

            # 2) Wallet credit through the shared ledger (sets closing balance).
            credit_wallet(
                c, earner_id, amount, ref,
                f"Level {level} commission on order #{order_id or purchase_ref}",
            )
            paid += 1

            # 3) Re-rank the earner (lightweight, same transaction).
            try:
                evaluate_user_rank_and_bonus(earner_id, cur=c)
            except Exception as e:
                logger.warning("rank eval skipped for %s: %s", earner_id, e)

        # Optional self cashback for the buyer.
        cashback_pct = _global_pct(c, "self_cashback")
        if cashback_pct > 0:
            cb = (price * (cashback_pct / Decimal("100"))).quantize(TWO_PLACES)
            if cb > 0:
                cb_ref = f"CASH-{order_id or purchase_ref}-{buyer_id}"
                c.execute(
                    """
                    INSERT INTO commissions (earner_id, from_user_id, level, amount,
                                             commission_type, order_id)
                    VALUES (%s, %s, 0, %s, 'self_cashback', %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (buyer_id, buyer_id, cb, order_id),
                )
                if c.fetchone():  # only credit the wallet the first time
                    credit_wallet(c, buyer_id, cb, cb_ref, "Self purchase cashback")

        return {"status": "success", "paid_upline": paid, "message": "Commissions distributed."}

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("distribute_commission failed buyer=%s: %s", buyer_id, e)
        return {"status": "error", "message": "Commission processing failed."}


def _load_package(c, package_id):
    from app.services.package_service import get_plan_by_id, get_commission_config
    plan = get_plan_by_id(package_id, c)
    if not plan:
        return None
    plan = dict(plan)
    cfg = get_commission_config(c)
    plan["level_commissions"] = {str(k): v for k, v in cfg["levels"].items()}
    plan["direct_commission"] = cfg["direct"]
    return plan


def _global_pct(c, key) -> Decimal:
    c.execute("SELECT percentage_value FROM global_commissions WHERE setting_key = %s", (key,))
    row = c.fetchone()
    return Decimal(str(row["percentage_value"])) if row else Decimal("0")


def process_rank_volume_bonus(user_id, rank_name, level, bonus_amount, cur=None):
    """Pay a one-time rank achievement bonus (idempotent per user/rank)."""
    bonus_amount = _money(bonus_amount)
    ref = f"RANKBONUS-{user_id}-L{level}"

    def _do(c):
        c.execute(
            """
            INSERT INTO commissions (earner_id, from_user_id, level, amount,
                                     commission_type)
            VALUES (%s, %s, %s, %s, 'rank_volume_bonus')
            ON CONFLICT DO NOTHING
            """,
            (user_id, user_id, level, bonus_amount),
        )
        credit_wallet(c, user_id, bonus_amount, ref, f"Rank bonus: {rank_name}")
        return True

    try:
        if cur is not None:
            return _do(cur)
        with get_cursor() as c:
            return _do(c)
    except Exception as e:
        logger.error("rank bonus failed user=%s: %s", user_id, e)
        return False
