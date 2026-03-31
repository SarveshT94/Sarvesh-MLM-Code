from app.db import get_cursor


def force_wallet_adjust(user_id, amount, action, remark, admin_id):

    cursor = get_cursor()

    try:

        # Start transaction
        cursor.execute("BEGIN")

        # Lock wallet row
        cursor.execute("""
            SELECT balance
            FROM wallets
            WHERE user_id = %s
            FOR UPDATE
        """, (user_id,))

        wallet = cursor.fetchone()

        if not wallet:
            raise Exception("Wallet not found")

        current_balance = wallet["balance"]

        # Validate action
        if action not in ["credit", "debit"]:
            raise Exception("Invalid action")

        # Calculate new balance
        if action == "credit":
            new_balance = current_balance + amount

        if action == "debit":

            if current_balance < amount:
                raise Exception("Insufficient balance")

            new_balance = current_balance - amount

        # Update wallet balance
        cursor.execute("""
            UPDATE wallets
            SET balance = %s
            WHERE user_id = %s
        """, (new_balance, user_id))

        # Insert ledger record
        cursor.execute("""
            INSERT INTO wallet_ledger
            (user_id, amount, txn_type, remark, created_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user_id,
            amount,
            action,
            remark,
            admin_id
        ))

        # Insert audit log
        cursor.execute("""
            INSERT INTO admin_audit_logs
            (admin_id, action, target_user_id, amount, remark)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            admin_id,
            action,
            user_id,
            amount,
            remark
        ))

        # Commit transaction
        cursor.execute("COMMIT")

        return {
            "old_balance": current_balance,
            "new_balance": new_balance
        }

    except Exception as e:

        cursor.execute("ROLLBACK")

        raise e
