from app.db import get_cursor
from decimal import Decimal
from app.services.wallet_service import credit_wallet, debit_wallet

# -----------------------------------
# Get All Pending Withdrawals (WITH DEDUCTIONS)
# -----------------------------------
def get_pending_withdrawals():
    """
    Fetches pending withdrawals and dynamically calculates TDS and Admin charges.
    """
    with get_cursor() as cur:
        # 1. Fetch live deduction percentages from global settings
        cur.execute("SELECT setting_key, percentage_value FROM global_commissions WHERE setting_key IN ('tds_deduction', 'admin_charge')")
        settings = {row['setting_key']: Decimal(str(row['percentage_value'])) for row in cur.fetchall()}
        
        tds_pct = settings.get('tds_deduction', Decimal('5.00'))
        admin_pct = settings.get('admin_charge', Decimal('5.00'))

        # 2. Fetch the pending requests
        cur.execute("""
            SELECT w.id, w.user_id, u.full_name, u.email, u.phone, w.amount, w.status, w.created_at
            FROM withdraw_requests w
            JOIN users u ON w.user_id = u.id
            WHERE w.status = 'pending'
            ORDER BY w.created_at ASC
        """)
        requests = cur.fetchall()

        # 3. Calculate exact net payable amounts
        for req in requests:
            gross_amount = Decimal(str(req['amount']))
            req['tds_amount'] = (gross_amount * tds_pct) / Decimal('100')
            req['admin_fee'] = (gross_amount * admin_pct) / Decimal('100')
            req['net_payable'] = gross_amount - req['tds_amount'] - req['admin_fee']

        return requests


# -----------------------------------
# Approve Withdrawal
# -----------------------------------
def approve_withdrawal(request_id, admin_id):
    """
    Marks withdrawal as approved (money leaves system).
    """
    with get_cursor() as cur:
        # Lock request
        cur.execute("SELECT * FROM withdraw_requests WHERE id = %s FOR UPDATE", (request_id,))
        request = cur.fetchone()

        if not request or request['status'] != 'pending':
            return {"status": "error", "message": "Request not found or already processed."}

        # Update status
        cur.execute("""
            UPDATE withdraw_requests 
            SET status = 'approved', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (request_id,))

        return {
            "status": "success",
            "message": f"Withdrawal of ₹{request['amount']} approved successfully."
        }


# -----------------------------------
# Reject Withdrawal (WITH SAFE REFUND)
# -----------------------------------
def reject_withdrawal(request_id, admin_id, reason):
    """
    Reject withdrawal and safely refund wallet.
    """
    with get_cursor() as cur:
        # Lock request
        cur.execute("SELECT * FROM withdraw_requests WHERE id = %s FOR UPDATE", (request_id,))
        request = cur.fetchone()

        if not request or request['status'] != 'pending':
            return {"status": "error", "message": "Request not found or already processed."}

        # Update status
        cur.execute("""
            UPDATE withdraw_requests 
            SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (request_id,))

        # Refund using wallet service
        credit_wallet(
            cur,
            request['user_id'],
            request['amount'],
            reference=f"withdraw_refund_{request_id}",
            description=f"Refund for rejected withdrawal #{request_id}. Reason: {reason}"
        )

        return {
            "status": "success",
            "message": "Withdrawal rejected and amount refunded safely."
        }

# -----------------------------------
# ADMIN WALLET ADJUSTMENT
# -----------------------------------
def admin_wallet_adjust(user_id, amount, action, admin_id, remark=""):
    """Admin can credit or debit user wallet manually."""
    try:
        with get_cursor() as cur:
            if amount <= 0:
                return {"status": "error", "message": "Invalid amount"}

            reference = f"admin_{action}_{admin_id}"

            if action == "credit":
                credit_wallet(cur, user_id, amount, reference=reference, description=remark or "Admin credit")
            elif action == "debit":
                debit_wallet(cur, user_id, amount, reference=reference, description=remark or "Admin debit")
            else:
                return {"status": "error", "message": "Invalid action"}

            return {"status": "success", "message": f"Wallet {action} successful"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
