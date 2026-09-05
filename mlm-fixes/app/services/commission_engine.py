"""
app/services/commission_engine.py  —  COMMISSION ENGINE (E-commerce + MLM)

All percentages are soft-coded (global_commissions / commission_plan tables).
Every payout is written to `commissions` (idempotent per earner/order/level)
AND to the member's wallet ledger in the SAME transaction as the order.

Payout types
------------
ACTIVATION / UPGRADE order (cart matched a plan tier):
    self_cashback %            -> buyer                         (level 0, 'self_cashback')
    direct_referral %          -> Level-1 sponsor               (level 1, 'direct_referral')
    commission_plan L2..L10 %  -> upline levels 2..10           (level n, 'level_income')
    (rank bonuses are evaluated afterwards by rank_service)

REPURCHASE order (member already active, any amount):
    repurchase_cashback %      -> buyer                         (level 0, 'repurchase_cashback')
    repurchase_referral %      -> Level-1 sponsor               (level 1, 'repurchase_referral')
    NO level income.

Amounts are always calculated on the ORDER AMOUNT actually paid (which for a
plan match equals the tier price).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.db import get_cursor
from app.services.sponsor_service import get_sponsor_chain
from app.services.wallet_service import credit_wallet

logger = logging.getLogger(__name__)
TWO = Decimal("0.01")


def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(TWO)


def _globals(c) -> dict:
    c.execute("SELECT setting_key, percentage_value FROM global_commissions")
    return {r["setting_key"]: Decimal(str(r["percentage_value"])) for r in c.fetchall()}


def _levels(c) -> dict:
    c.execute("SELECT level, percentage FROM commission_plan WHERE is_active = TRUE")
    rows = c.fetchall()
    if rows:
        return {int(r["level"]): Decimal(str(r["percentage"])) for r in rows}
    c.execute("SELECT level, commission_percentage FROM level_commissions")
    return {int(r["level"]): Decimal(str(r["commission_percentage"])) for r in c.fetchall()}


def _pay(c, earner_id, from_user_id, level, amount, ctype, order_id, ref, desc) -> bool:
    """Insert commission (idempotent) + credit wallet. Returns True if paid now."""
    if amount <= 0:
        return False
    c.execute(
        """
        INSERT INTO commissions (earner_id, from_user_id, level, amount, commission_type, order_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (earner_id, from_user_id, level, amount, ctype, order_id),
    )
    if not c.fetchone():
        return False  # already paid for this order/earner/level
    credit_wallet(c, earner_id, amount, ref, desc)
    return True


# ===========================================================================
# ACTIVATION / UPGRADE
# ===========================================================================
def distribute_commission(buyer_id, package_id, order_id=None, cur=None,
                          purchase_ref=None, amount=None):
    """
    Pay activation/upgrade commissions for `order_id`.
    `amount` = order amount actually paid (defaults to the plan price).
    Runs inside the caller's transaction when `cur` is given.
    """
    from app.services.rank_service import evaluate_user_rank_and_bonus

    def _run(c):
        c.execute("SELECT id, name, price FROM subscription_plans WHERE id = %s", (package_id,))
        plan = c.fetchone()
        if not plan:
            return {"status": "error", "message": "Plan not found."}
        base = _money(amount if amount is not None else plan["price"])
        g = _globals(c)
        levels = _levels(c)
        direct_pct = g.get("direct_referral", g.get("direct_commission", levels.get(1, Decimal("0"))))
        cashback_pct = g.get("self_cashback", Decimal("0"))
        oid = order_id
        tag = oid or purchase_ref or f"{buyer_id}-{package_id}"

        paid = 0
        # 1) Self cashback to the buyer
        cb = _money(base * cashback_pct / 100)
        if _pay(c, buyer_id, buyer_id, 0, cb, "self_cashback", oid, f"CASH-{tag}-{buyer_id}",
                f"{cashback_pct}% self cashback on order #{tag}"):
            paid += 1

        # 2) Upline: direct (L1) + level income (L2..N)
        for sp in get_sponsor_chain(buyer_id, cur=c):
            earner, level = sp["user_id"], int(sp["level"])
            if level == 1:
                pct, ctype, label = direct_pct, "direct_referral", "Direct referral"
            else:
                pct, ctype, label = levels.get(level, Decimal("0")), "level_income", f"Level {level} income"
            amt = _money(base * pct / 100)
            if _pay(c, earner, buyer_id, level, amt, ctype, oid, f"COMM-{tag}-{earner}-L{level}",
                    f"{pct}% {label} from member #{buyer_id} (order #{tag})"):
                paid += 1
                try:
                    evaluate_user_rank_and_bonus(earner, cur=c)
                except Exception as e:
                    logger.warning("rank eval skipped for %s: %s", earner, e)
        return {"status": "success", "paid": paid, "base_amount": float(base)}

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("distribute_commission failed buyer=%s: %s", buyer_id, e, exc_info=True)
        return {"status": "error", "message": "Commission processing failed."}


# ===========================================================================
# REPURCHASE
# ===========================================================================
def distribute_repurchase(buyer_id, order_id, amount, cur=None):
    """Repurchase cashback (buyer) + repurchase referral (direct sponsor)."""
    def _run(c):
        base = _money(amount)
        g = _globals(c)
        cb_pct = g.get("repurchase_cashback", Decimal("0"))
        ref_pct = g.get("repurchase_referral", Decimal("0"))
        paid = 0
        cb = _money(base * cb_pct / 100)
        if _pay(c, buyer_id, buyer_id, 0, cb, "repurchase_cashback", order_id,
                f"RCASH-{order_id}-{buyer_id}", f"{cb_pct}% repurchase cashback on order #{order_id}"):
            paid += 1
        c.execute("SELECT sponsor_id FROM users WHERE id = %s", (buyer_id,))
        row = c.fetchone()
        if row and row["sponsor_id"]:
            amt = _money(base * ref_pct / 100)
            if _pay(c, row["sponsor_id"], buyer_id, 1, amt, "repurchase_referral", order_id,
                    f"RREF-{order_id}-{row['sponsor_id']}",
                    f"{ref_pct}% repurchase referral from member #{buyer_id} (order #{order_id})"):
                paid += 1
        return {"status": "success", "paid": paid, "base_amount": float(base)}

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("distribute_repurchase failed buyer=%s: %s", buyer_id, e, exc_info=True)
        return {"status": "error", "message": "Repurchase commission failed."}


# ===========================================================================
# RANK BONUS
# ===========================================================================
def process_rank_volume_bonus(user_id, rank_name, level, bonus_amount, cur=None):
    """Pay a one-time rank achievement bonus (idempotent per user/rank)."""
    bonus_amount = _money(bonus_amount)
    ref = f"RANKBONUS-{user_id}-L{level}"

    def _do(c):
        c.execute("SELECT 1 FROM wallet_ledger WHERE reference_id = %s", (ref,))
        if c.fetchone():
            return False
        c.execute(
            """
            INSERT INTO commissions (earner_id, from_user_id, level, amount, commission_type)
            VALUES (%s, %s, %s, %s, 'rank_bonus')
            """,
            (user_id, user_id, level, bonus_amount),
        )
        credit_wallet(c, user_id, bonus_amount, ref, f"Rank achievement bonus: {rank_name}")
        return True

    try:
        if cur is not None:
            return _do(cur)
        with get_cursor() as c:
            return _do(c)
    except Exception as e:
        logger.error("rank bonus failed user=%s: %s", user_id, e)
        return False
