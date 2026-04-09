from app.db import get_cursor
from decimal import Decimal


# -----------------------------------
# Get Exact Wallet Balance
# -----------------------------------
def get_wallet_balance(user_id):
    """
    Enterprise Standard: Calculates real balance dynamically from ledger.
    """
    try:
        with get_cursor() as cur:
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

            balance = total_in - total_out

            return {
                "status": "success",
                "balance": float(balance)
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error fetching balance: {str(e)}"
        }


# -----------------------------------
# Wallet Transaction History (🔥 FIXED ERROR)
# -----------------------------------
def get_wallet_history(user_id):
    """
    Fetch wallet transaction history
    """
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, amount, transaction_type, reference, created_at
                FROM wallet_ledger
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 100
            """, (user_id,))

            transactions = cur.fetchall()

            return {
                "status": "success",
                "data": transactions
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error fetching history: {str(e)}"
        }


# -----------------------------------
# Process Safe Withdrawal Request
# -----------------------------------
def request_withdrawal(user_id, amount):
    """
    Safely processes withdrawal with race-condition protection
    """
    try:
        requested_amount = Decimal(str(amount))

        if requested_amount <= 0:
            return {
                "status": "error",
                "message": "Withdrawal amount must be greater than zero."
            }

        with get_cursor() as cur:
            # 🔒 Row Lock (prevents double spend)
            cur.execute(
                "SELECT id FROM users WHERE id = %s FOR UPDATE",
                (user_id,)
            )

            # 🔍 Get real balance
            cur.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN transaction_type LIKE '%%credit%%' THEN amount ELSE 0 END), 0) as total_in,
                    COALESCE(SUM(CASE WHEN transaction_type LIKE '%%debit%%' THEN amount ELSE 0 END), 0) as total_out
                FROM wallet_ledger
                WHERE user_id = %s
            """, (user_id,))

            result = cur.fetchone()

            balance = Decimal(str(result['total_in'])) - Decimal(str(result['total_out']))

            # ❌ Insufficient balance
            if balance < requested_amount:
                return {
                    "status": "error",
                    "message": f"Insufficient funds. Current balance: {float(balance)}"
                }

            # 💸 Ledger debit (lock funds)
            cur.execute("""
                INSERT INTO wallet_ledger
                (user_id, amount, transaction_type, reference)
                VALUES (%s, %s, %s, %s)
            """, (
                user_id,
                requested_amount,
                "withdrawal_debit",
                "Pending Admin Approval"
            ))

            # 📋 Create withdrawal request
            cur.execute("""
                INSERT INTO withdraw_requests
                (user_id, amount, status)
                VALUES (%s, %s, %s)
            """, (
                user_id,
                requested_amount,
                "Pending"
            ))

            return {
                "status": "success",
                "message": "Withdrawal requested successfully."
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Withdrawal failed: {str(e)}"
        }


# -----------------------------------
# Debit Wallet (Reusable Core Function)
# -----------------------------------
def debit_wallet(user_id, amount, reference=""):
    """
    Safely debit wallet (used by withdrawals, purchases, etc.)
    """
    try:
        amount = Decimal(str(amount))

        if amount <= 0:
            return {
                "status": "error",
                "message": "Invalid debit amount"
            }

        with get_cursor() as cur:
            # 🔒 Lock user row
            cur.execute(
                "SELECT id FROM users WHERE id = %s FOR UPDATE",
                (user_id,)
            )

            # 🔍 Calculate balance
            cur.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN transaction_type LIKE '%%credit%%' THEN amount ELSE 0 END), 0) as total_in,
                    COALESCE(SUM(CASE WHEN transaction_type LIKE '%%debit%%' THEN amount ELSE 0 END), 0) as total_out
                FROM wallet_ledger
                WHERE user_id = %s
            """, (user_id,))

            result = cur.fetchone()
            balance = Decimal(str(result['total_in'])) - Decimal(str(result['total_out']))

            # ❌ Check balance
            if balance < amount:
                return {
                    "status": "error",
                    "message": "Insufficient balance"
                }

            # 💸 Insert debit entry
            cur.execute("""
                INSERT INTO wallet_ledger
                (user_id, amount, transaction_type, reference)
                VALUES (%s, %s, %s, %s)
            """, (
                user_id,
                amount,
                "debit",
                reference or "Wallet debit"
            ))

            return {
                "status": "success",
                "message": "Amount debited successfully"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
