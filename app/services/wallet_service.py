from app.db import get_cursor
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# =========================================================
# INTERNAL BALANCE CALCULATION
# =========================================================
def _calculate_balance(cur, user_id):
    cur.execute("""
        SELECT COALESCE(SUM(
            CASE 
                WHEN transaction_type = 'credit' THEN amount
                WHEN transaction_type = 'debit' THEN -amount
            END
        ), 0) as balance
        FROM wallet_ledger
        WHERE user_id = %s
    """, (user_id,))

    result = cur.fetchone()
    return Decimal(str(result["balance"]))


# =========================================================
# PUBLIC BALANCE
# =========================================================
def get_wallet_balance(cur, user_id):
    return _calculate_balance(cur, user_id)


# =========================================================
# WALLET HISTORY
# =========================================================
def get_wallet_history(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, amount, transaction_type, reference_id, description, closing_balance, created_at
                FROM wallet_ledger
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 100
            """, (user_id,))

            return {
                "status": "success",
                "data": cur.fetchall()
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# =========================================================
# CORE LEDGER ENGINE (IMMUTABLE + IDEMPOTENT)
# =========================================================
def _create_ledger_entry(cur, user_id, amount, txn_type, reference, description):

    # 🚨 Idempotency check
    cur.execute("""
        SELECT id FROM wallet_ledger
        WHERE reference_id = %s
        LIMIT 1
    """, (reference,))

    if cur.fetchone():
        raise Exception(f"Duplicate transaction reference: {reference}")

    # 🔒 Lock user
    cur.execute(
        "SELECT id FROM users WHERE id = %s FOR UPDATE",
        (user_id,)
    )

    current_balance = _calculate_balance(cur, user_id)

    if txn_type == "debit" and current_balance < amount:
        raise Exception("Insufficient balance")

    # Calculate closing balance
    closing_balance = (
        current_balance + amount if txn_type == "credit"
        else current_balance - amount
    )

    # Immutable insert
    cur.execute("""
        INSERT INTO wallet_ledger
        (user_id, amount, transaction_type, reference_id, description, closing_balance, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """, (
        user_id,
        amount,
        txn_type,
        reference,
        description,
        closing_balance
    ))

    logger.info(
        f"[LEDGER] user={user_id} type={txn_type} amount={amount} closing={closing_balance} ref={reference}"
    )

    return closing_balance


# =========================================================
# CREDIT
# =========================================================
def credit_wallet(cur, user_id, amount, reference, description="credit"):
    amount = Decimal(str(amount))

    if amount <= 0:
        raise Exception("Invalid credit amount")

    return _create_ledger_entry(
        cur, user_id, amount, "credit", reference, description
    )


# =========================================================
# DEBIT
# =========================================================
def debit_wallet(cur, user_id, amount, reference, description="debit"):
    amount = Decimal(str(amount))

    if amount <= 0:
        raise Exception("Invalid debit amount")

    return _create_ledger_entry(
        cur, user_id, amount, "debit", reference, description
    )
