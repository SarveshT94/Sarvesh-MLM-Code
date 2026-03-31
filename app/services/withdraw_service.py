from app.db import get_db_connection
from app.services.wallet_service import get_wallet_balance, debit_wallet


# ----------------------------------
# CREATE WITHDRAW REQUEST
# ----------------------------------

def create_withdraw_request(user_id, amount):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        if amount <= 0:
            return {
                "success": False,
                "message": "Invalid withdraw amount"
            }

        # Check wallet balance
        balance = get_wallet_balance(user_id)

        if balance < amount:
            return {
                "success": False,
                "message": "Insufficient wallet balance"
            }

        # Prevent multiple pending requests
        cur.execute("""
            SELECT id
            FROM withdraw_requests
            WHERE user_id=%s
            AND status='pending'
            LIMIT 1
        """, (user_id,))

        pending = cur.fetchone()

        if pending:
            return {
                "success": False,
                "message": "You already have a pending withdraw request"
            }

        # Create request
        cur.execute("""
            INSERT INTO withdraw_requests
            (user_id, amount)
            VALUES (%s,%s)
            RETURNING id
        """, (user_id, amount))

        request_id = cur.fetchone()["id"]

        conn.commit()

        return {
            "success": True,
            "request_id": request_id
        }

    except Exception as e:

        conn.rollback()
        raise e

    finally:

        cur.close()
        conn.close()


# ----------------------------------
# ADMIN WITHDRAW QUEUE
# ----------------------------------

def get_withdraw_requests(limit=100, offset=0):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                wr.id,
                wr.user_id,
                wr.amount,
                wr.status,
                wr.requested_at,
                wr.processed_at,
                u.full_name,
                u.phone
            FROM withdraw_requests wr
            JOIN users u ON u.id = wr.user_id
            ORDER BY wr.requested_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


# ----------------------------------
# APPROVE WITHDRAW
# ----------------------------------

def approve_withdraw(request_id):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT user_id, amount, status
            FROM withdraw_requests
            WHERE id=%s
        """, (request_id,))

        request = cur.fetchone()

        if not request:
            raise Exception("Withdraw request not found")

        if request["status"] != "pending":
            raise Exception("Request already processed")

        user_id = request["user_id"]
        amount = request["amount"]

        # Debit wallet
        debit_wallet(
            user_id,
            amount,
            f"withdraw_{request_id}",
            "Withdraw approved"
        )

        # Update request
        cur.execute("""
            UPDATE withdraw_requests
            SET status='approved',
                processed_at=NOW()
            WHERE id=%s
        """, (request_id,))

        conn.commit()

        return True

    except Exception as e:

        conn.rollback()
        raise e

    finally:

        cur.close()
        conn.close()


# ----------------------------------
# REJECT WITHDRAW
# ----------------------------------

def reject_withdraw(request_id, remark=None):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            UPDATE withdraw_requests
            SET status='rejected',
                processed_at=NOW(),
                admin_note=%s
            WHERE id=%s
            AND status='pending'
        """, (remark, request_id))

        conn.commit()

        return True

    finally:

        cur.close()
        conn.close()
