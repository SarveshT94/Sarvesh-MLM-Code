from app.db import get_cursor
from decimal import Decimal


# -----------------------------------
# INTERNAL: Calculate Balance
# -----------------------------------
def _calculate_balance(cur, user_id):
    cur.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type LIKE '%%credit%%' THEN amount ELSE 0 END), 0) as total_in,
            COALESCE(SUM(CASE WHEN transaction_type LIKE '%%debit%%' THEN amount ELSE 0 END), 0) as total_out
        FROM wallet_ledger
        WHERE user_id = %s
    """, (user_id,))

    result = cur.fetchone()

    total_in = Decimal(str(result['total_in']))
    total_out = Decimal(str(result['total_out']))

    return total_in - total_out


# -----------------------------------
# Get Wallet Balance (Flexible)
# -----------------------------------
def get_wallet_balance(cur, user_id):
    """
    MUST be called with cursor (enterprise standard)
    Returns Decimal
    """
    return _calculate_balance(cur, user_id)


# -----------------------------------
# Wallet History (API Safe)
# -----------------------------------
def get_wallet_history(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, amount, transaction_type, reference, created_at
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


# -----------------------------------
# Debit Wallet (CORE - TRANSACTION SAFE)
# -----------------------------------
def debit_wallet(cur, user_id, amount, reference="", description=""):
    """
    MUST be used inside transaction
    """

    amount = Decimal(str(amount))

    if amount <= 0:
        raise Exception("Invalid debit amount")

    # 🔒 Lock user
    cur.execute(
        "SELECT id FROM users WHERE id = %s FOR UPDATE",
        (user_id,)
    )

    balance = _calculate_balance(cur, user_id)

    if balance < amount:
        raise Exception("Insufficient balance")

    cur.execute("""
        INSERT INTO wallet_ledger
        (user_id, amount, transaction_type, reference_id, description, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (
        user_id,
        amount,
        "debit",
        reference or "wallet_debit",
        description or "Wallet debit"
    ))

    return True


# -----------------------------------
# Credit Wallet (OPTIONAL - GOOD PRACTICE)
# -----------------------------------
def credit_wallet(cur, user_id, amount, reference="", description=""):
    """
    Standard credit function (use in commissions later)
    """

    amount = Decimal(str(amount))

    if amount <= 0:
        raise Exception("Invalid credit amount")

    cur.execute("""
        INSERT INTO wallet_ledger
        (user_id, amount, transaction_type, reference_id, description, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (
        user_id,
        amount,
        "credit",
        reference or "wallet_credit",
        description or "Wallet credit"
    ))

    return True
