from app.db import get_cursor
from decimal import Decimal

# -----------------------------------
# GET USER RANK & GAMIFICATION DATA 
# (Powers the Dashboard Progress Bar)
# -----------------------------------
def get_user_rank_data(user_id):
    """Calculates infinite downline volume and determines the user's gamification progress."""
    with get_cursor() as cur:
        # 1. Calculate Total Team Volume (Infinite Depth)
        cur.execute("""
            WITH RECURSIVE downline AS (
                SELECT id FROM users WHERE sponsor_id = %s
                UNION ALL
                SELECT u.id FROM users u INNER JOIN downline d ON u.sponsor_id = d.id
            )
            SELECT COALESCE(SUM(amount), 0) as total_volume 
            FROM user_packages 
            WHERE user_id IN (SELECT id FROM downline)
        """, (user_id,))
        
        vol_result = cur.fetchone()
        current_volume = Decimal(str(vol_result['total_volume'])) if vol_result else Decimal('0.00')

        # 2. Get Current Rank based on VOLUME
        cur.execute("""
            SELECT id, name, min_volume, reward FROM ranks 
            WHERE min_volume <= %s 
            ORDER BY min_volume DESC LIMIT 1
        """, (current_volume,))
        current_rank_row = cur.fetchone()
        current_rank_name = current_rank_row['name'] if current_rank_row else 'Active Affiliate'
        current_rank_id = current_rank_row['id'] if current_rank_row else None

        # 3. Get Next Rank (The Goal)
        cur.execute("""
            SELECT name, min_volume, reward FROM ranks 
            WHERE min_volume > %s 
            ORDER BY min_volume ASC LIMIT 1
        """, (current_volume,))
        next_rank_row = cur.fetchone()

        if next_rank_row:
            next_rank_name = next_rank_row['name']
            next_rank_volume = Decimal(str(next_rank_row['min_volume']))
            # Calculate progress percentage safely
            if next_rank_volume > 0:
                progress = (current_volume / next_rank_volume) * Decimal('100.00')
            else:
                progress = Decimal('0.00')
        else:
            next_rank_name = "Max Rank Reached"
            next_rank_volume = current_volume
            progress = Decimal('100.00')

        # 4. SILENT BACKGROUND UPDATE: Lock in the new rank ID in the users table
        if current_rank_id:
            cur.execute("""
                UPDATE users SET rank_id = %s WHERE id = %s AND (rank_id IS NULL OR rank_id != %s)
            """, (current_rank_id, user_id, current_rank_id))

        return {
            "current_rank": current_rank_name,
            "next_rank": next_rank_name,
            "current_volume": float(current_volume),
            "next_rank_volume": float(next_rank_volume),
            "progress_percentage": float(min(progress, Decimal('100.00')))
        }


# -----------------------------------
# LEGACY: CHECK & UPDATE USER RANK
# (Kept for backward compatibility)
# -----------------------------------
def check_and_update_rank(user_id, cur=None):
    """Updates user rank based on total sales volume (Upgraded from team_size)."""
    def _process(cur):
        # 1. Calculate Volume
        cur.execute("""
            WITH RECURSIVE downline AS (
                SELECT id FROM users WHERE sponsor_id = %s
                UNION ALL
                SELECT u.id FROM users u INNER JOIN downline d ON u.sponsor_id = d.id
            )
            SELECT COALESCE(SUM(amount), 0) as total_volume 
            FROM user_packages 
            WHERE user_id IN (SELECT id FROM downline)
        """, (user_id,))
        vol_result = cur.fetchone()
        current_volume = Decimal(str(vol_result['total_volume'])) if vol_result else Decimal('0.00')

        # 2. Find applicable rank
        cur.execute("""
            SELECT id FROM ranks WHERE min_volume <= %s ORDER BY min_volume DESC LIMIT 1
        """, (current_volume,))
        rank = cur.fetchone()
        if not rank: return

        # 3. Update rank if changed
        cur.execute("SELECT rank_id FROM users WHERE id = %s", (user_id,))
        user_data = cur.fetchone()
        current_rank = user_data["rank_id"] if user_data else None

        if rank["id"] != current_rank:
            cur.execute("UPDATE users SET rank_id = %s WHERE id = %s", (rank["id"], user_id))

    if cur:
        _process(cur)
    else:
        with get_cursor() as new_cur:
            _process(new_cur)


# -----------------------------------
# LEGACY: GET USER RANK
# -----------------------------------
def get_user_rank(user_id):
    with get_cursor() as cur:
        cur.execute("""
            SELECT r.name AS rank_name
            FROM users u
            JOIN ranks r ON u.rank_id = r.id
            WHERE u.id = %s
        """, (user_id,))
        return cur.fetchone()
