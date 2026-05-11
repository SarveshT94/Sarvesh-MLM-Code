from app.db import get_cursor
from app.services.wallet_service import credit_wallet, debit_wallet
import logging

logger = logging.getLogger(__name__)


def force_wallet_adjust(user_id, amount, action, remark, admin_id):
    """
    BUG FIXED #4:
    - Was using cursor = get_cursor() directly then calling cursor.execute("BEGIN").
      This crashes because get_cursor() is a context manager not a cursor.
    - Was querying the 'wallets' table which doesn't exist.
      The system uses wallet_ledger + wallet_service for all balance operations.
    - Manual BEGIN/COMMIT is now removed — get_cursor() handles transactions.

    Now delegates to the existing credit_wallet/debit_wallet in wallet_service,
    which handles locking, balance checks, and ledger entries correctly.
    """
    if action not in ("credit", "debit"):
        raise ValueError("Invalid action. Must be 'credit' or 'debit'.")

    if float(amount) <= 0:
        raise ValueError("Amount must be greater than zero.")

    with get_cursor() as cur:

        if action == "credit":
            reference = f"admin_credit_{admin_id}_{user_id}"
            new_balance = credit_wallet(
                cur, user_id, amount,
                reference=reference,
                description=remark or "Admin manual credit"
            )
        else:
            reference = f"admin_debit_{admin_id}_{user_id}"
            new_balance = debit_wallet(
                cur, user_id, amount,
                reference=reference,
                description=remark or "Admin manual debit"
            )

        # Audit log
        cur.execute("""
            INSERT INTO audit_logs
            (action, user_id, admin_id, metadata, status, created_at)
            VALUES (%s, %s, %s, %s::jsonb, 'success', NOW())
        """, (
            f"admin_wallet_{action}",
            user_id,
            admin_id,
            f'{{"amount": {amount}, "remark": "{remark}"}}'
        ))

        logger.info(f"Admin wallet {action} | user={user_id} | amount={amount} "
                    f"| admin={admin_id} | new_balance={new_balance}")

    return {"new_balance": float(new_balance)}
