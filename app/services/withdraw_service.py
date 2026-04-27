from app.db import get_cursor
from decimal import Decimal
from app.services.wallet_service import get_wallet_balance, debit_wallet
from app.ml.fraud_detector import calculate_user_risk_score
from app.services.audit_service import log_action
import logging

logger = logging.getLogger(__name__)


# =========================================================
# CREATE WITHDRAW REQUEST
# =========================================================
def create_withdraw_request(user_id, amount, payout_method="bank", payout_details=""):
    try:
        amount = Decimal(str(amount))

        if amount <= 0:
            return {"success": False, "message": "Invalid withdraw amount"}

        with get_cursor() as cur:

            # 🔒 Lock user row
            cur.execute(
                "SELECT id FROM users WHERE id = %s FOR UPDATE",
                (user_id,)
            )

            # 🔥 FIXED: Extract the actual number from the dictionary we created in the last step
            balance_data = get_wallet_balance(cur, user_id)
            current_balance = Decimal(str(balance_data.get("balance", 0)))

            if current_balance < amount:
                return {"success": False, "message": "Insufficient balance"}

            # Prevent multiple pending requests
            cur.execute("""
                SELECT id FROM withdraw_requests
                WHERE user_id=%s AND status='pending'
                LIMIT 1
            """, (user_id,))

            if cur.fetchone():
                return {"success": False, "message": "Pending request exists"}

            # Insert request with UPI/Bank details
            cur.execute("""
                INSERT INTO withdraw_requests (user_id, amount, payout_method, payout_details)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (user_id, amount, payout_method, payout_details))

            request_id = cur.fetchone()["id"]

            # ✅ Audit (Added payout method to tracking)
            log_action(
                action="withdraw_request_created",
                user_id=user_id,
                metadata={
                    "amount": str(amount), 
                    "request_id": request_id,
                    "payout_method": payout_method
                }
            )

        return {"success": True, "request_id": request_id, "message": "Withdrawal requested successfully!"}

    except Exception as e:
        logger.error(f"Withdraw request failed | {str(e)}")

        log_action(
            action="withdraw_request_failed",
            user_id=user_id,
            metadata={"amount": str(amount), "error": str(e)},
            status="failed"
        )

        raise


# ----------------------------------
# ADMIN WITHDRAW QUEUE
# ----------------------------------
def get_withdraw_requests(limit=100, offset=0):
    try:
        with get_cursor() as cur:

            cur.execute("""
                SELECT
                    wr.id,
                    wr.user_id,
                    wr.amount,
                    wr.status,
                    wr.requested_at,
                    wr.processed_at,
                    u.full_name,
                    u.phone,

                    -- ✅ Legal TDS calculation (2%% under Section 194H)
                    (wr.amount * 0.02) as tds_amount,

                    -- ✅ Admin Fee calculation (Updated to 5%% as requested)
                    (wr.amount * 0.05) as admin_fee, 

                    -- ✅ Net payout after subtracting both
                    (wr.amount - (wr.amount * 0.02) - (wr.amount * 0.05)) as net_payable

                FROM withdraw_requests wr
                JOIN users u ON u.id = wr.user_id
                ORDER BY wr.requested_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))

            return cur.fetchall()

    except Exception as e:
        logger.error(f"Withdraw fetch error: {str(e)}")
        return []

# =========================================================
# APPROVE WITHDRAW
# =========================================================
def approve_withdraw(request_id, admin_id=None):
    try:
        with get_cursor() as cur:

            cur.execute("""
                SELECT user_id, amount, status
                FROM withdraw_requests
                WHERE id=%s
                FOR UPDATE
            """, (request_id,))

            request = cur.fetchone()

            if not request:
                raise Exception("Request not found")

            if request["status"] != "pending":
                raise Exception("Already processed")

            user_id = request["user_id"]
            amount = Decimal(str(request["amount"]))

            # 🚨 Risk Check
            risk = calculate_user_risk_score(user_id)

            if risk["risk_level"] == "high":
                raise Exception(f"High risk user: {risk['reasons']}")

            # 💰 Debit wallet
            debit_wallet(
                cur,
                user_id,
                amount,
                reference=f"withdraw_{request_id}",
                description="Withdraw approved"
            )

            # ✅ Update
            cur.execute("""
                UPDATE withdraw_requests
                SET status='approved', processed_at=NOW()
                WHERE id=%s AND status='pending'
            """, (request_id,))

            if cur.rowcount == 0:
                raise Exception("Race condition detected")

            # ✅ Audit
            log_action(
                action="withdraw_approved",
                user_id=user_id,
                admin_id=admin_id,
                metadata={"amount": str(amount), "request_id": request_id}
            )

        return True

    except Exception as e:
        logger.error(f"Withdraw approval failed | {str(e)}")

        log_action(
            action="withdraw_approve_failed",
            metadata={"request_id": request_id, "error": str(e)},
            status="failed"
        )

        raise


# =========================================================
# REJECT WITHDRAW
# =========================================================
def reject_withdraw(request_id, remark=None, admin_id=None):
    try:
        with get_cursor() as cur:

            cur.execute("""
                SELECT user_id, status
                FROM withdraw_requests
                WHERE id=%s
                FOR UPDATE
            """, (request_id,))

            request = cur.fetchone()

            if not request:
                raise Exception("Request not found")

            if request["status"] != "pending":
                raise Exception("Already processed")

            user_id = request["user_id"]

            cur.execute("""
                UPDATE withdraw_requests
                SET status='rejected',
                    processed_at=NOW(),
                    admin_note=%s
                WHERE id=%s AND status='pending'
            """, (remark, request_id))

            # ✅ Audit
            log_action(
                action="withdraw_rejected",
                user_id=user_id,
                admin_id=admin_id,
                metadata={"request_id": request_id, "remark": remark}
            )

        return True

    except Exception as e:
        logger.error(f"Withdraw reject failed | {str(e)}")

        log_action(
            action="withdraw_reject_failed",
            metadata={"request_id": request_id, "error": str(e)},
            status="failed"
        )

        raise
