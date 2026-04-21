from app.db import get_cursor
from app.services.sponsor_service import get_sponsor_chain
from app.services.package_service import get_package_by_id
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def distribute_commission(buyer_id, package_id, purchase_ref=None):
    """
    Enterprise Dynamic Commission Engine (Upgraded)

    Improvements:
    - Stronger idempotency
    - Better logging
    - Safer calculations
    - Future-ready for purchase tracking
    """

    try:
        # 1. Load package
        package = get_package_by_id(package_id)
        if not package:
            return {"status": "error", "message": "Package not found or inactive."}

        purchase_amount = Decimal(str(package['price']))
        direct_bonus = Decimal(str(package['direct_commission'] or 0))
        level_rules = package.get('level_commissions') or {}

        # Optional unique reference (future-safe)
        reference = purchase_ref or f"{buyer_id}-{package_id}"

        # 2. Get sponsor chain
        sponsors = get_sponsor_chain(buyer_id)

        if not sponsors:
            logger.info(f"No sponsors found for user {buyer_id}")
            return {"status": "success", "message": "No commissions applicable."}

        # 3. Process commissions
        with get_cursor() as cur:
            for level, sponsor_id in enumerate(sponsors, start=1):

                str_level = str(level)

                # A. Level commission
                level_commission = Decimal('0')
                if str_level in level_rules:
                    percent = Decimal(str(level_rules[str_level]))
                    level_commission = (purchase_amount * percent).quantize(Decimal('0.01'))

                # B. Direct bonus
                total_commission = level_commission
                if level == 1 and direct_bonus > 0:
                    total_commission += direct_bonus

                if total_commission <= 0:
                    continue

                # 4. STRONGER IDEMPOTENCY CHECK
                cur.execute("""
                    SELECT id
                    FROM commissions
                    WHERE earner_id = %s
                    AND from_user_id = %s
                    AND level = %s
                    AND commission_type = %s
                """, (
                    sponsor_id,
                    buyer_id,
                    level,
                    f"{package['name']}|{reference}"
                ))

                if cur.fetchone():
                    logger.warning(
                        f"Duplicate commission prevented | user={buyer_id}, sponsor={sponsor_id}, level={level}"
                    )
                    continue

                # 5. Insert Commission
                commission_type = f"{package['name']}|{reference}"

                cur.execute("""
                    INSERT INTO commissions
                    (earner_id, from_user_id, level, amount, commission_type)
                    VALUES (%s,%s,%s,%s,%s)
                """, (
                    sponsor_id,
                    buyer_id,
                    level,
                    total_commission,
                    commission_type
                ))

                # 6. Wallet Entry (linked via same reference)
                cur.execute("""
                    INSERT INTO wallet_ledger
                    (user_id, amount, transaction_type, reference)
                    VALUES (%s,%s,%s,%s)
                """, (
                    sponsor_id,
                    total_commission,
                    "commission_credit",
                    f"{commission_type}"
                ))

                logger.info(
                    f"Commission added | sponsor={sponsor_id} | level={level} | amount={total_commission}"
                )

        return {"status": "success", "message": "Commissions distributed successfully."}

    except Exception as e:
        logger.error(f"Commission distribution failed: {str(e)}")
        return {"status": "error", "message": "Commission processing failed"}
