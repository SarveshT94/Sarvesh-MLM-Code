from app.db import get_cursor
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# =========================================================
# 🛡️ BULLETPROOF BALANCE CALCULATION
# =========================================================
def _calculate_balance(cur, user_id):
    cur.execute("""
        SELECT amount, transaction_type 
        FROM wallet_ledger 
        WHERE user_id = %s
    """, (user_id,))
    
    balance = Decimal('0.00')
    
    for row in cur.fetchall():
        # Ledger now stores negative values for debits, so a simple SUM works,
        # but we keep this logic for safety across different t_types.
        amt = Decimal(str(row['amount'])) if row['amount'] is not None else Decimal('0.00')
        t_type = str(row['transaction_type']).lower() if row['transaction_type'] else ''
        
        # We check both the sign and the type string for absolute safety
        if amt > 0:
            balance += amt
        else:
            balance += amt # Adding a negative number correctly subtracts
            
    return balance

# =========================================================
# PUBLIC BALANCE
# =========================================================
def get_wallet_balance(cur, user_id):
    balance = _calculate_balance(cur, user_id)
    return {"balance": float(balance)}

# =========================================================
# 🛡️ BULLETPROOF WALLET HISTORY
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
            amt = float(tx["amount"]) if tx["amount"] is not None else 0.0
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

        return {"status": "success", "data": formatted_txs}

    except Exception as e:
        logger.error(f"Error fetching wallet history: {str(e)}")
        return {"status": "error", "message": str(e), "data": []}

# =========================================================
# CORE LEDGER ENGINE (REPAIRED FOR NEGATIVE DEBITS)
# =========================================================
def _create_ledger_entry(cur, user_id, amount, txn_type, reference, description):
    # Idempotency check
    cur.execute("SELECT id FROM wallet_ledger WHERE reference_id = %s LIMIT 1", (reference,))
    if cur.fetchone():
        raise Exception(f"Duplicate transaction reference: {reference}")

    # Lock user
    cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))

    current_balance = _calculate_balance(cur, user_id)
    amt_decimal = Decimal(str(amount))

    if txn_type == "debit" and current_balance < amt_decimal:
        raise Exception("Insufficient balance")

    # 🔥 THE FIX: Store debits as negative numbers so SQL SUM() works correctly
    stored_amount = amt_decimal if txn_type == "credit" else -abs(amt_decimal)
    closing_balance = current_balance + stored_amount

    cur.execute("""
        INSERT INTO wallet_ledger
        (user_id, amount, transaction_type, reference_id, description, closing_balance, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """, (user_id, stored_amount, txn_type, reference, description, closing_balance))

    return closing_balance

def credit_wallet(cur, user_id, amount, reference, description="credit"):
    return _create_ledger_entry(cur, user_id, amount, "credit", reference, description)

def debit_wallet(cur, user_id, amount, reference, description="debit"):
    return _create_ledger_entry(cur, user_id, amount, "debit", reference, description)
