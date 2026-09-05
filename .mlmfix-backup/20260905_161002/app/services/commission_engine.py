from app.db import get_cursor
from app.services.sponsor_service import get_sponsor_chain
# ✅ FIX: Using the function that actually grabs dynamic commissions
from app.services.package_service import get_plan_with_commissions
from decimal import Decimal
import logging
import uuid
import time

logger = logging.getLogger(__name__)

def distribute_commission(buyer_id, package_id, purchase_ref=None):
    from app.services.rank_service import evaluate_user_rank_and_bonus

    try:
        # ✅ FIX: Grab the package details AND the dynamic commission percentages
        package = get_plan_with_commissions(package_id)
        if not package:
            return {"status": "error", "message": "Package not found or inactive."}

        purchase_amount = Decimal(str(package['price']))
        
        # ✅ FIX: Convert direct bonus to proper percentage (divide by 100)
        direct_percent = Decimal(str(package.get('direct_commission') or 0))
        direct_bonus = (purchase_amount * (direct_percent / Decimal('100'))).quantize(Decimal('0.01'))
        
        level_rules = package.get('level_commissions') or {}

        # FIX: Ensure true uniqueness if reference isn't provided to prevent double-skips
        reference = purchase_ref or f"{buyer_id}-{package_id}-{int(time.time())}-{uuid.uuid4().hex[:6]}"

        sponsors = get_sponsor_chain(buyer_id)
        if not sponsors:
            return {"status": "success", "message": "No commissions applicable."}

        # The MASTER TRANSACTION Block
        with get_cursor() as cur:
            # FIX: Do not use enumerate. Unpack the dictionary returned by CTE.
            for sponsor in sponsors:
                sponsor_id = sponsor['user_id']
                level = sponsor['level']
                str_level = str(level)

                level_commission = Decimal('0')
                if str_level in level_rules:
                    # ✅ FIX: Convert level commission to proper percentage (divide by 100)
                    percent = Decimal(str(level_rules[str_level]))
                    level_commission = (purchase_amount * (percent / Decimal('100'))).quantize(Decimal('0.01'))

                total_commission = level_commission
                if level == 1 and direct_bonus > 0:
                    total_commission += direct_bonus

                if total_commission <= 0:
                    continue

                commission_type = f"{package['name']}|{reference}"

                # Idempotency Check
                cur.execute("""
                    SELECT id FROM commissions
                    WHERE earner_id = %s AND from_user_id = %s AND level = %s AND commission_type = %s
                """, (sponsor_id, buyer_id, level, commission_type))

                if cur.fetchone():
                    logger.warning(f"Duplicate prevented | user={buyer_id}, sponsor={sponsor_id}")
                    continue

                # Insert Commission
                cur.execute("""
                    INSERT INTO commissions (earner_id, from_user_id, level, amount, commission_type)
                    VALUES (%s,%s,%s,%s,%s)
                """, (sponsor_id, buyer_id, level, total_commission, commission_type))

                # Wallet Entry
                cur.execute("""
                    INSERT INTO wallet_ledger (user_id, amount, transaction_type, reference)
                    VALUES (%s,%s,%s,%s)
                """, (sponsor_id, total_commission, "commission_credit", commission_type))

                # FIX: Pass the ACTIVE cursor so the rank evaluation stays in THIS transaction!
                evaluate_user_rank_and_bonus(sponsor_id, cur)

        return {"status": "success", "message": "Commissions distributed successfully."}

    except Exception as e:
        logger.error(f"Commission distribution failed: {str(e)}")
        return {"status": "error", "message": "Commission processing failed"}

def process_rank_volume_bonus(user_id, rank_name, level, bonus_amount, cur=None):
    try:
        reference_str = f"VOL_BONUS_L{level}_{rank_name.upper()}"

        def _execute_wallet_credit(cursor):
            cursor.execute("""
                INSERT INTO commissions (earner_id, from_user_id, level, amount, commission_type)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, user_id, level, bonus_amount, reference_str))

            cursor.execute("""
                INSERT INTO wallet_ledger (user_id, amount, transaction_type, reference)
                VALUES (%s, %s, %s, %s)
            """, (user_id, bonus_amount, "rank_volume_bonus", reference_str))

        if cur:
            _execute_wallet_credit(cur)
        else:
            with get_cursor() as new_cur:
                _execute_wallet_credit(new_cur)
        return True
    except Exception as e:
        logger.error(f"Failed to process rank volume bonus for {user_id}: {str(e)}")
        return False
