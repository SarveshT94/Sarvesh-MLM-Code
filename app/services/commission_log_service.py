import logging
from decimal import Decimal
from datetime import datetime
from app.db import get_cursor
from app.services.wallet_service import credit_wallet

logger = logging.getLogger(__name__)


def _get_team_volume(cur, sponsor_id):
    """Recursive CTE to get total downline purchase volume."""
    cur.execute("""
        WITH RECURSIVE downline AS (
            SELECT id FROM users WHERE sponsor_id = %s
            UNION ALL
            SELECT u.id FROM users u INNER JOIN downline d ON u.sponsor_id = d.id
        )
        SELECT COALESCE(SUM(amount), 0) AS total_volume
        FROM user_packages
        WHERE user_id IN (SELECT id FROM downline)
    """, (sponsor_id,))
    result = cur.fetchone()
    return Decimal(str(result['total_volume'])) if result else Decimal('0.00')


def distribute_package_commissions(cur, purchaser_id, package_price, purchase_ref=None):
    """
    Master Commission Engine — distributes cashback, direct referral,
    10-level commissions, and team target bonuses.

    BUG FIXED #17 & #18 — Duplicate reference collision on multiple purchases:
    Old references used static keys like:
        "self_cashback_{user_id}"
        "direct_referral_{purchaser_id}_{level}"
    If the same user bought a second package, the wallet_service idempotency
    check found the same reference and threw "Duplicate transaction reference",
    silently failing the entire second purchase.

    Fix: references now include a timestamp + purchase_ref so each purchase
    gets a unique reference. Pass purchase_ref from the calling code for
    deterministic idempotency (re-running same purchase won't double-credit).
    """
    price = Decimal(str(package_price))

    # Generate a unique token for this specific purchase event
    purchase_token = purchase_ref or f"p{purchaser_id}_{int(datetime.utcnow().timestamp())}"

    # 1. Fetch Global Percentages
    cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
    globals_data = {
        row['setting_key']: Decimal(str(row['percentage_value']))
        for row in cur.fetchall()
    }
    cashback_pct = globals_data.get('self_cashback', Decimal('5.00'))
    direct_pct   = globals_data.get('direct_referral', Decimal('10.00'))

    # 2. Fetch Level Percentages
    cur.execute("SELECT level, commission_percentage FROM level_commissions ORDER BY level ASC")
    level_pcts = {row['level']: Decimal(str(row['commission_percentage'])) for row in cur.fetchall()}


    # ---- STEP 1: Self Cashback ----
    cashback_amount = (price * cashback_pct) / Decimal('100')
    if cashback_amount > 0:
        # FIXED: reference now includes purchase_token — unique per purchase
        credit_wallet(
            cur, purchaser_id, cashback_amount,
            reference=f"cashback_{purchaser_id}_{purchase_token}",
            description=f"{cashback_pct}% Cashback on purchase"
        )
        _log_commission(cur, purchaser_id, purchaser_id, 0, cashback_amount, 'cashback')

    # ---- STEP 2: Trace Upline ----
    cur.execute("""
        WITH RECURSIVE upline AS (
            SELECT id, sponsor_id, 1 AS distance
            FROM users
            WHERE id = (SELECT sponsor_id FROM users WHERE id = %s)
            UNION ALL
            SELECT u.id, u.sponsor_id, up.distance + 1
            FROM users u INNER JOIN upline up ON u.id = up.sponsor_id
        )
        SELECT id AS upline_id, distance AS level FROM upline
    """, (purchaser_id,))
    upline_tree = cur.fetchall()

    # ---- STEP 3: Distribute Up the Tree ----
    for node in upline_tree:
        upline_id = node['upline_id']
        level     = node['level']

        if not upline_id:
            continue

        comm_amount = Decimal('0.00')
        comm_type   = ''
        desc        = ''

        if level == 1:
            comm_amount = (price * direct_pct) / Decimal('100')
            comm_type   = 'direct_referral'
            desc        = f"{direct_pct}% Direct Referral from User #{purchaser_id}"

        elif level <= 10:
            pct = level_pcts.get(level, Decimal('0'))
            if pct > 0:
                comm_amount = (price * pct) / Decimal('100')
                comm_type   = 'level_commission'
                desc        = f"{pct}% Level {level} Commission from User #{purchaser_id}"

        if comm_amount > 0:
            # FIXED: reference includes purchase_token — unique per purchase event
            credit_wallet(
                cur, upline_id, comm_amount,
                reference=f"{comm_type}_{purchaser_id}_{level}_{purchase_token}",
                description=desc
            )
            _log_commission(cur, upline_id, purchaser_id, level, comm_amount, comm_type)

        # Team Target Bonus
        team_volume      = _get_team_volume(cur, upline_id)
        target_bonus_pct = Decimal('0.00')

        for tier in target_tiers:
            min_vol = Decimal(str(tier['min_volume']))
            max_vol = Decimal(str(tier['max_volume']))
            if min_vol <= team_volume <= max_vol:
                target_bonus_pct = Decimal(str(tier['bonus_percentage']))
                break

        if target_bonus_pct > 0:
            target_bonus = (price * target_bonus_pct) / Decimal('100')
            credit_wallet(
                cur, upline_id, target_bonus,
                # FIXED: include purchase_token for uniqueness
                reference=f"target_bonus_{purchaser_id}_{level}_{purchase_token}",
                description=f"{target_bonus_pct}% Team Target Bonus (Vol: ₹{team_volume})"
            )
            _log_commission(cur, upline_id, purchaser_id, level, target_bonus, 'team_target_bonus')


def _log_commission(cur, earner_id, from_user_id, level, amount, comm_type):
    cur.execute("""
        INSERT INTO commissions
        (earner_id, from_user_id, level, amount, commission_type, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (earner_id, from_user_id, level, amount, comm_type))


def get_commission_logs(limit=100, offset=0):
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.created_at,
                    c.amount,
                    c.commission_type AS type,
                    c.commission_type AS description,
                    u.id AS user_id,
                    u.full_name,
                    COALESCE(NULLIF(u.phone, ''), 'Not Provided')       AS earner_phone,
                    COALESCE(NULLIF(s.full_name, ''), 'Root User')      AS referrer_name,
                    f.id                                                  AS trigger_user_id,
                    COALESCE(NULLIF(f.full_name, ''), 'System')         AS trigger_user_name,
                    COALESCE(NULLIF(f.phone, ''), 'Not Provided')       AS trigger_phone,
                    COALESCE(NULLIF(sp.name, ''), 'Legacy Package')     AS plan_name
                FROM commissions c
                JOIN users u ON u.id = c.earner_id
                LEFT JOIN users s ON u.sponsor_id = s.id
                LEFT JOIN users f ON f.id = c.from_user_id
                LEFT JOIN (
                    SELECT DISTINCT ON (user_id) user_id, package_id
                    FROM user_packages
                    ORDER BY user_id, created_at DESC
                ) latest_pkg ON latest_pkg.user_id = f.id
                LEFT JOIN subscription_plans sp ON sp.id = latest_pkg.package_id
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching commission logs: {str(e)}")
        return []


def get_user_commission_logs(user_id, limit=50, offset=0):
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.created_at,
                    c.amount,
                    c.commission_type AS type,
                    f.full_name AS trigger_user_name
                FROM commissions c
                LEFT JOIN users f ON f.id = c.from_user_id
                WHERE c.earner_id = %s
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, limit, offset))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching user commission logs: {str(e)}")
        return []


# Backward compatibility wrappers
def distribute_commission(cur, from_user_id, purchase_amount):
    return distribute_package_commissions(cur, from_user_id, purchase_amount)

def process_commission(cur, from_user_id, purchase_amount):
    return distribute_package_commissions(cur, from_user_id, purchase_amount)
