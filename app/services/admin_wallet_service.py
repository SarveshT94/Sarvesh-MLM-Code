from app.db import get_cursor
from decimal import Decimal

# -----------------------------------
# Get All Pending Withdrawals
# -----------------------------------
def get_pending_withdrawals():
    """
    Fetches all pending payouts for the Admin Dashboard.
    Joins with the users table to get the member's name and email.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT w.id, w.user_id, u.full_name, u.email, w.amount, w.status, w.created_at
            FROM withdraw_requests w
            JOIN users u ON w.user_id = u.id
            WHERE w.status = 'Pending'
            ORDER BY w.created_at ASC
        """)
        return cur.fetchall()

# -----------------------------------
# Approve Withdrawal (Money Leaves Company)
# -----------------------------------
def approve_withdrawal(request_id, admin_id):
    """
    Locks the request, marks it as paid. 
    (In a fully deployed system, this is where you trigger the Razorpay/Stripe API).
    """
    with get_cursor() as cur:
        # 1. Lock the request so multiple admins can't double-pay it
        cur.execute("SELECT * FROM withdraw_requests WHERE id = %s FOR UPDATE", (request_id,))
        request = cur.fetchone()
        
        if not request or request['status'] != 'Pending':
            return {"status": "error", "message": "Request not found or already processed."}

        # 2. Update the request status
        cur.execute("""
            UPDATE withdraw_requests 
            SET status = 'Approved', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (request_id,))
        
        return {"status": "success", "message": f"Withdrawal of {request['amount']} approved successfully."}

# -----------------------------------
# Reject Withdrawal (Safe Auto-Refund)
# -----------------------------------
def reject_withdrawal(request_id, admin_id, reason):
    """
    Enterprise Standard: If a payout is rejected, the funds MUST be 
    safely credited back to the user's ledger so their balance is restored.
    """
    with get_cursor() as cur:
        # 1. Lock the request
        cur.execute("SELECT * FROM withdraw_requests WHERE id = %s FOR UPDATE", (request_id,))
        request = cur.fetchone()
        
        if not request or request['status'] != 'Pending':
            return {"status": "error", "message": "Request not found or already processed."}

        # 2. Update status to Rejected
        cur.execute("""
            UPDATE withdraw_requests 
            SET status = 'Rejected', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (request_id,))

        # 3. CRITICAL: Refund the user's wallet via Double-Entry Bookkeeping
        cur.execute("""
            INSERT INTO wallet_ledger
            (user_id, amount, transaction_type, reference)
            VALUES (%s, %s, %s, %s)
        """, (
            request['user_id'], 
            request['amount'], 
            "withdrawal_refund", 
            f"Refund for rejected withdrawal #{request_id}. Reason: {reason}"
        ))

        return {"status": "success", "message": "Withdrawal rejected. Funds have been safely returned to the user's wallet."}
