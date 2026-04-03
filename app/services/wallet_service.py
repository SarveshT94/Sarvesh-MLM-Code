from app.db import get_cursor
from decimal import Decimal

# -----------------------------------
# Get Exact Wallet Balance
# -----------------------------------
def get_wallet_balance(user_id):
    """
    Enterprise Standard: Calculates real balance dynamically from the ledger.
    Never rely on a single 'balance' column that can be easily manipulated.
    """
    with get_cursor() as cur:
        # Sum all credits and subtract all debits. COALESCE ensures we don't get 'None' errors.
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
# Process Safe Withdrawal Request
# -----------------------------------
def request_withdrawal(user_id, amount):
    """
    Safely processes a withdrawal request ensuring no overdrafts or 
    double-click race conditions.
    """
    requested_amount = Decimal(str(amount))
    
    if requested_amount <= 0:
        return {"status": "error", "message": "Withdrawal amount must be greater than zero."}

    with get_cursor() as cur:
        # 1. Row-Level Locking (Enterprise Anti-Fraud)
        # Locks the user row for milliseconds so they can't double-click and bypass the balance check
        cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        
        # 2. Get true balance
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type LIKE '%%credit%%' THEN amount ELSE 0 END), 0) as total_in,
                COALESCE(SUM(CASE WHEN transaction_type LIKE '%%debit%%' THEN amount ELSE 0 END), 0) as total_out
            FROM wallet_ledger
            WHERE user_id = %s
        """, (user_id,))
        
        result = cur.fetchone()
        balance = Decimal(str(result['total_in'])) - Decimal(str(result['total_out']))
        
        # 3. Check for sufficient funds
        if balance < requested_amount:
            return {"status": "error", "message": f"Insufficient funds. Current balance: {balance}"}
            
        # 4. Create the Ledger Debit (Locks the money so it can't be spent elsewhere)
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
        
        # 5. Send to Admin Dashboard for final review/payout
        cur.execute("""
            INSERT INTO withdraw_requests
            (user_id, amount, status)
            VALUES (%s, %s, %s)
        """, (
            user_id, 
            requested_amount, 
            "Pending"
        ))
        
        return {"status": "success", "message": "Withdrawal requested successfully."}
