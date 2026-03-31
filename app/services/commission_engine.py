from app.db import get_cursor
from app.services.sponsor_service import get_sponsor_chain
from app.config.commission_levels import COMMISSION_LEVELS


def distribute_commission(user_id, purchase_amount):
    """
    Enterprise MLM Commission Engine
    """

    sponsors = get_sponsor_chain(user_id)

    with get_cursor() as cur:

        for level, sponsor_id in enumerate(sponsors, start=1):

            if level not in COMMISSION_LEVELS:
                break

            percent = COMMISSION_LEVELS[level]

            commission_amount = purchase_amount * percent

            # Duplicate Protection
            cur.execute("""
                SELECT id
                FROM commissions
                WHERE earner_id = %s
                AND from_user_id = %s
                AND level = %s
            """, (sponsor_id, user_id, level))

            exists = cur.fetchone()

            if exists:
                continue

            # Insert Commission Log
            cur.execute("""
                INSERT INTO commissions
                (earner_id, from_user_id, level, amount, commission_type)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                sponsor_id,
                user_id,
                level,
                commission_amount,
                "referral_commission"
            ))

            # Wallet Credit
            cur.execute("""
                INSERT INTO wallet_ledger
                (user_id, amount, transaction_type, reference)
                VALUES (%s,%s,%s,%s)
            """, (
                sponsor_id,
                commission_amount,
                "commission_credit",
                f"Level {level} commission from user {user_id}"
            ))

    return True
