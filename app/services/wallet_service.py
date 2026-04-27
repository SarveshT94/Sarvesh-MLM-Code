from app.db import get_cursor
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# =========================================================
# 🛡️ BULLETPROOF BALANCE CALCULATION
# Completely avoids Postgres ENUM/LIKE casting crashes
# =========================================================
def _calculate_balance(cur, user_id):
    cur.execute("""
        SELECT amount, transaction_type 
        FROM wallet_ledger 
        WHERE user_id = %s
    """, (user_id,))
    
    balance = Decimal('0.00')
    
    for row in cur.fetchall():
        # Safely convert to string and lower case in Python to avoid DB crashes
        amt = Decimal(str(row['amount'])) if row['amount'] is not None else Decimal('0.00')
        t_type = str(row['transaction_type']).lower() if row['transaction_type'] else ''
        
        # 🔥 FIXED TYPO HERE: Changed 'ttype' to 't_type'
        if 'credit' in t_type or 'in' in t_type:
            balance += amt
        elif 'debit' in t_type or 'out' in t_type:
            balance -= amt
            
    return balance


# =========================================================
# PUBLIC BALANCE
# =========================================================
def get_wallet_balance(cur, user_id):
    balance = _calculate_balance(cur, user_id)
    return {"balance": float(balance)}


# =========================================================
# 🛡️ BULLETPROOF WALLET HISTORY
# Safely handles NULL closing balances without vanishing
# =========================================================
def get_wallet_history(cur, user_id):
    try:
        cur.execute("""
            SELECT id, amount, transaction_type, reference_id, description, closing_balance, created_at
            FROM wallet_ledger
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (user_id,))

        transactions = cur.fetchall()
        formatted_txs = []
        
        for tx in transactions:
            # Safely handle amounts
            amt = float(tx["amount"]) if tx["amount"] is not None else 0.0
            t_type_str = str(tx["transaction_type"]).lower()
            
            if 'debit' in t_type_str or 'out' in t_type_str:
                amt = -abs(amt)
                
            # Safely handle closing balance (Prevents the Vanishing History Bug!)
            closing_bal = float(tx["closing_balance"]) if tx.get("closing_balance") is not None else 0.0

            formatted_txs.append({
                "id": tx["id"],
                "amount": amt,
                "transaction_type": tx["transaction_type"] or "System",
                "reference": tx["reference_id"] or f"TXN-{tx['id']}",
                "description": tx["description"] or "Wallet Transaction",
                "closing_balance": closing_bal,
                "created_at": tx["created_at"].isoformat() if tx["created_at"] else None
            })

        return {
            "status": "success",
            "data": formatted_txs
        }

    except Exception as e:
        logger.error(f"Error fetching wallet history: {str(e)}")
        # Returning an empty list safely if all else fails
        return {"status": "error", "message": str(e), "data": []}


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
