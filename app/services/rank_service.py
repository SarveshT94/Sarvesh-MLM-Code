from app.db import get_cursor
from decimal import Decimal
from app.services.team_service import get_total_team_count
import logging

logger = logging.getLogger(__name__)

def get_user_rank_data(user_id):
    with get_cursor() as cur:
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

        team_size = get_total_team_count(user_id, max_depth=50)

        cur.execute("SELECT rank_level FROM users WHERE id = %s", (user_id,))
        user_row = cur.fetchone()
        current_rank_level = user_row['rank_level'] if user_row and user_row['rank_level'] else 0

        cur.execute("SELECT rank_name FROM rank_rules WHERE level = %s", (current_rank_level,))
        current_rank_row = cur.fetchone()
        current_rank_name = current_rank_row['rank_name'] if current_rank_row else 'Associate'

        cur.execute("""
            SELECT rank_name, req_business_vol, req_team_size FROM rank_rules 
            WHERE level > %s ORDER BY level ASC LIMIT 1
        """, (current_rank_level,))
        next_rank_row = cur.fetchone()

        if next_rank_row:
            next_rank_name = next_rank_row['rank_name']
            next_rank_volume = Decimal(str(next_rank_row['req_business_vol']))
            next_team_size = next_rank_row['req_team_size']
            
            if next_rank_volume > 0:
                progress = (current_volume / next_rank_volume) * Decimal('100.00')
            else:
                progress = Decimal('0.00')
        else:
            next_rank_name = "Max Rank Reached"
            next_rank_volume = current_volume
            next_team_size = team_size
            progress = Decimal('100.00')

        return {
            "current_rank": current_rank_name,
            "next_rank": next_rank_name,
            "current_volume": float(current_volume),
            "next_rank_volume": float(next_rank_volume),
            "current_team_size": team_size,
            "next_rank_team_size": next_team_size,
            "progress_percentage": float(min(progress, Decimal('100.00')))
        }

# FIX: Added cur=None to allow execution within an existing transaction
def evaluate_user_rank_and_bonus(user_id, cur=None):
    from app.services.commission_engine import process_rank_volume_bonus

    def _execute_rank_check(cursor):
        cursor.execute("""
            WITH RECURSIVE downline AS (
                SELECT id FROM users WHERE sponsor_id = %s
                UNION ALL
                SELECT u.id FROM users u INNER JOIN downline d ON u.sponsor_id = d.id
            )
            SELECT COALESCE(SUM(amount), 0) as total_volume 
            FROM user_packages 
            WHERE user_id IN (SELECT id FROM downline)
        """, (user_id,))
        
        vol_result = cursor.fetchone()
        current_volume = Decimal(str(vol_result['total_volume'])) if vol_result else Decimal('0.00')
        team_size = get_total_team_count(user_id, max_depth=50)

        cursor.execute("SELECT rank_level FROM users WHERE id = %s", (user_id,))
        user_row = cursor.fetchone()
        current_rank_level = user_row['rank_level'] if user_row and user_row['rank_level'] else 0

        cursor.execute("SELECT * FROM rank_rules ORDER BY level ASC")
        rules = cursor.fetchall()

        highest_eligible_rank_level = 0
        
        for rule in rules:
            level = rule['level']
            req_vol = Decimal(str(rule['req_business_vol']))
            req_size = rule['req_team_size']
            bonus_pct = Decimal(str(rule['bonus_percentage']))

            if current_volume >= req_vol:
                cursor.execute("SELECT id FROM user_bonus_history WHERE user_id = %s AND rank_level = %s", (user_id, level))
                already_paid = cursor.fetchone()

                if not already_paid:
                    bonus_amount = (req_vol * (bonus_pct / Decimal('100.00'))).quantize(Decimal('0.01'))
                    cursor.execute("""
                        INSERT INTO user_bonus_history (user_id, rank_level, bonus_amount)
                        VALUES (%s, %s, %s)
                    """, (user_id, level, bonus_amount))
                    
                    process_rank_volume_bonus(user_id, rule['rank_name'], level, bonus_amount, cursor)

            if current_volume >= req_vol and team_size >= req_size:
                highest_eligible_rank_level = level

        if highest_eligible_rank_level > current_rank_level:
            cursor.execute("UPDATE users SET rank_level = %s WHERE id = %s", (highest_eligible_rank_level, user_id))
            logger.info(f"User {user_id} promoted to Rank Level {highest_eligible_rank_level}")
            
        return {"status": "success", "current_volume": float(current_volume), "team_size": team_size}

    try:
        # Route execution based on whether a cursor was passed down from a higher level
        if cur:
            return _execute_rank_check(cur)
        else:
            with get_cursor() as new_cur:
                return _execute_rank_check(new_cur)
    except Exception as e:
        logger.error(f"Error evaluating rank and bonus for user {user_id}: {str(e)}")
        return {"status": "error", "message": "Evaluation failed"}

def get_user_rank(user_id):
    with get_cursor() as cur:
        cur.execute("""
            SELECT r.rank_name
            FROM users u
            JOIN rank_rules r ON u.rank_level = r.level
            WHERE u.id = %s
        """, (user_id,))
        return cur.fetchone()
