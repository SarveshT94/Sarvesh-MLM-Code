from app.db import get_cursor
from app.services.wallet_service import credit_wallet


# -----------------------------------
# Get All Pending Withdrawals
# -----------------------------------
def get_pending_withdrawals():
    """
    Fetch all pending withdrawals for admin dashboard.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT w.id, w.user_id, u.full_name, u.email, w.amount, w.status, w.created_at
            FROM withdraw_requests w
            JOIN users u ON w.user_id = u.id
            WHERE w.status = 'pending'
            ORDER BY w.created_at ASC
        """)
        return cur.fetchall()


# -----------------------------------
# Approve Withdrawal
# -----------------------------------
def approve_withdrawal(request_id, admin_id):
    """
    Marks withdrawal as approved (money leaves system).
    """
    with get_cursor() as cur:

        # 🔒 Lock request
        cur.execute("""
            SELECT * FROM withdraw_requests
            WHERE id = %s
            FOR UPDATE
        """, (request_id,))

        request = cur.fetchone()

        if not request or request['status'] != 'pending':
            return {"status": "error", "message": "Request not found or already processed."}

        # ✅ Update status
        cur.execute("""
            UPDATE withdraw_requests 
            SET status = 'approved',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (request_id,))

        return {
            "status": "success",
            "message": f"Withdrawal of {request['amount']} approved successfully."
        }


# -----------------------------------
# Reject Withdrawal (WITH SAFE REFUND)
# -----------------------------------
def reject_withdrawal(request_id, admin_id, reason):
    """
    Reject withdrawal and safely refund wallet.
    """
    with get_cursor() as cur:

        # 🔒 Lock request
        cur.execute("""
            SELECT * FROM withdraw_requests
            WHERE id = %s
            FOR UPDATE
        """, (request_id,))

        request = cur.fetchone()

        if not request or request['status'] != 'pending':
            return {"status": "error", "message": "Request not found or already processed."}

        # ✅ Update status
        cur.execute("""
            UPDATE withdraw_requests 
            SET status = 'rejected',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (request_id,))

        # ✅ Refund using wallet service (IMPORTANT)
        credit_wallet(
            cur,
            request['user_id'],
            request['amount'],
            reference=f"withdraw_refund_{request_id}",
            description=f"Refund for rejected withdrawal #{request_id}. Reason: {reason}"
        )

        return {
            "status": "success",
            "message": "Withdrawal rejected and amount refunded successfully."
        }


# -----------------------------------
# ADMIN WALLET ADJUSTMENT (🔥 NEW)
# -----------------------------------

from app.services.wallet_service import credit_wallet, debit_wallet


def admin_wallet_adjust(user_id, amount, action, admin_id, remark=""):
    """
    Admin can credit or debit user wallet manually.

    action: 'credit' or 'debit'
    """

    try:
        with get_cursor() as cur:

            if amount <= 0:
                return {"status": "error", "message": "Invalid amount"}

            reference = f"admin_{action}_{admin_id}"

            if action == "credit":
                credit_wallet(
                    cur,
                    user_id,
                    amount,
                    reference=reference,
                    description=remark or "Admin credit"
                )

            elif action == "debit":
                debit_wallet(
                    cur,
                    user_id,
                    amount,
                    reference=reference,
                    description=remark or "Admin debit"
                )

            else:
                return {"status": "error", "message": "Invalid action"}

            return {
                "status": "success",
                "message": f"Wallet {action} successful"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
