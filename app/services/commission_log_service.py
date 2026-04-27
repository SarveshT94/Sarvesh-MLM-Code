import logging
from decimal import Decimal
from app.db import get_cursor
from app.services.wallet_service import credit_wallet

logger = logging.getLogger(__name__)

# =================================================================
# HELPER: CALCULATE TOTAL NETWORK SALES VOLUME
# =================================================================
def _get_team_volume(cur, sponsor_id):
    """
    Uses a Recursive CTE to find all downline members infinitely deep,
    then sums their total package purchases.
    """
    cur.execute("""
        WITH RECURSIVE downline AS (
            SELECT id FROM users WHERE sponsor_id = %s
            UNION ALL
            SELECT u.id FROM users u INNER JOIN downline d ON u.sponsor_id = d.id
        )
        SELECT COALESCE(SUM(amount), 0) as total_volume 
        FROM user_packages 
        WHERE user_id IN (SELECT id FROM downline)
    """, (sponsor_id,))
    result = cur.fetchone()
    return Decimal(str(result['total_volume'])) if result else Decimal('0.00')


# =================================================================
# MASTER COMMISSION ENGINE (DYNAMIC)
# =================================================================
def distribute_package_commissions(cur, purchaser_id, package_price):
    """
    Executes the dynamic 10-level commission, direct referral, target bonuses, and cashback.
    MUST be called inside an active transaction cursor to ensure database safety.
    """
    price = Decimal(str(package_price))

    # 1. Fetch Global Percentages (Cashback & Direct Referral)
    cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
    globals_data = {row['setting_key']: Decimal(str(row['percentage_value'])) for row in cur.fetchall()}

    cashback_pct = globals_data.get('self_cashback', Decimal('5.00'))
    direct_pct = globals_data.get('direct_referral', Decimal('10.00'))

    # 2. Fetch Level Percentages (Levels 2-10)
    cur.execute("SELECT level, commission_percentage FROM level_commissions ORDER BY level ASC")
    level_pcts = {row['level']: Decimal(str(row['commission_percentage'])) for row in cur.fetchall()}

    # 3. Fetch Team Target Bonus Tiers
    cur.execute("SELECT min_volume, max_volume, bonus_percentage FROM team_target_bonuses ORDER BY min_volume ASC")
    target_tiers = cur.fetchall()

    # ==========================================
    # STEP 1: Process Self-Cashback
    # ==========================================
    cashback_amount = (price * cashback_pct) / Decimal('100')
    if cashback_amount > 0:
        credit_wallet(
            cur, 
            purchaser_id, 
            cashback_amount, 
            reference=f"self_cashback_{purchaser_id}", 
            description=f"{cashback_pct}% Cashback on package purchase"
        )
        _log_commission(cur, purchaser_id, purchaser_id, 0, cashback_amount, 'cashback')

    # ==========================================
    # STEP 2: Trace the ENTIRE Upline Chain
    # ==========================================
    cur.execute("""
        WITH RECURSIVE upline AS (
            SELECT id, sponsor_id, 1 AS distance FROM users WHERE id = (SELECT sponsor_id FROM users WHERE id = %s)
            UNION ALL
            SELECT u.id, u.sponsor_id, up.distance + 1 FROM users u INNER JOIN upline up ON u.id = up.sponsor_id
        )
        SELECT id as upline_id, distance as level FROM upline;
    """, (purchaser_id,))

    upline_tree = cur.fetchall()

    # ==========================================
    # STEP 3: Distribute Money Up the Tree
    # ==========================================
    for node in upline_tree:
        upline_id = node['upline_id']
        level = node['level']

        if not upline_id:
            continue 

        comm_amount = Decimal('0.00')
        comm_type = ''
        desc = ''

        if level == 1:
            comm_amount = (price * direct_pct) / Decimal('100')
            comm_type = 'direct_referral'
            desc = f"{direct_pct}% Direct Referral from User #{purchaser_id}"
            
        elif level <= 10:
            pct = level_pcts.get(level, Decimal('0'))
            if pct > 0:
                comm_amount = (price * pct) / Decimal('100')
                comm_type = 'level_commission'
                desc = f"{pct}% Level {level} Commission from User #{purchaser_id}"

        if comm_amount > 0:
            credit_wallet(cur, upline_id, comm_amount, reference=f"{comm_type}_{purchaser_id}_{level}", description=desc)
            _log_commission(cur, upline_id, purchaser_id, level, comm_amount, comm_type)

        # Team Target Bonus (Infinite Depth)
        team_volume = _get_team_volume(cur, upline_id)
        target_bonus_pct = Decimal('0.00')
        
        for tier in target_tiers:
            min_vol = Decimal(str(tier['min_volume']))
            max_vol = Decimal(str(tier['max_volume']))
            if min_vol <= team_volume <= max_vol:
                target_bonus_pct = Decimal(str(tier['bonus_percentage']))
                break  

        if target_bonus_pct > 0:
            target_bonus_amount = (price * target_bonus_pct) / Decimal('100')
            credit_wallet(
                cur, 
                upline_id, 
                target_bonus_amount, 
                reference=f"team_target_bonus_{purchaser_id}_{level}", 
                description=f"{target_bonus_pct}% Team Target Bonus (Vol: ₹{team_volume})"
            )
            _log_commission(cur, upline_id, purchaser_id, level, target_bonus_amount, 'team_target_bonus')


# =================================================================
# INTERNAL LOGGING
# =================================================================
def _log_commission(cur, earner_id, from_user_id, level, amount, comm_type):
    """Records the specific transaction in the commissions table for the Admin UI."""
    cur.execute("""
        INSERT INTO commissions (earner_id, from_user_id, level, amount, commission_type, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (earner_id, from_user_id, level, amount, comm_type))


# =================================================================
# 📊 ADMIN DASHBOARD VIEWS (🔥 UPGRADED WITH LEGACY DATA FALLBACKS)
# =================================================================
def get_commission_logs(limit=100, offset=0):
    """
    Fetch commission logs mapped specifically for the interactive Admin Receipt Modal.
    Uses COALESCE to handle old "legacy" database records that are missing data.
    """
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
                    COALESCE(NULLIF(u.phone, ''), 'Not Provided') AS earner_phone, 
                    COALESCE(NULLIF(s.full_name, ''), 'Root User') AS referrer_name,
                    f.id AS trigger_user_id, 
                    COALESCE(NULLIF(f.full_name, ''), 'System') AS trigger_user_name,
                    COALESCE(NULLIF(f.phone, ''), 'Not Provided') AS trigger_phone,
                    COALESCE(NULLIF(sp.name, ''), 'Legacy Package') AS plan_name
                FROM commissions c
                JOIN users u ON u.id = c.earner_id
                LEFT JOIN users s ON u.sponsor_id = s.id  
                LEFT JOIN users f ON f.id = c.from_user_id  
                
                -- Isolate the Trigger User's latest package
                LEFT JOIN (
                    SELECT DISTINCT ON (user_id) user_id, package_id 
                    FROM user_packages 
                    ORDER BY user_id, created_at DESC
                ) latest_pkg ON latest_pkg.user_id = f.id
                
                -- Link to subscription_plans
                LEFT JOIN subscription_plans sp ON sp.id = latest_pkg.package_id
                
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))

            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching admin commission logs: {str(e)}")
        return []

# =================================================================
# 👤 USER FRONTEND VIEWS
# =================================================================
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


# =================================================================
# ⚠️ BACKWARD COMPATIBILITY WRAPPER
# (Prevents old code from crashing if it imports the old function name)
# =================================================================
def distribute_commission(cur, from_user_id, purchase_amount):
    return distribute_package_commissions(cur, from_user_id, purchase_amount)

def process_commission(cur, from_user_id, purchase_amount):
    return distribute_package_commissions(cur, from_user_id, purchase_amount)
