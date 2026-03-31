from app.db import get_db_connection


def get_wallet_balance(user_id):
    """
    Calculate wallet balance from ledger
    """

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as balance
            FROM wallet_ledger
            WHERE user_id = %s
        """, (user_id,))

        result = cur.fetchone()

        return result["balance"]

    finally:

        cur.close()
        conn.close()


def get_wallet_history(user_id, limit=50):
    """
    Fetch wallet transaction history
    """

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                id,
                transaction_type,
                amount,
                reference_id,
                description,
                created_at
            FROM wallet_ledger
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))

        rows = cur.fetchall()

        return rows

    finally:

        cur.close()
        conn.close()


def credit_wallet(user_id, amount, reference_id, description):
    """
    Credit wallet balance
    """

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO wallet_ledger
            (user_id, transaction_type, amount, reference_id, description, created_at)
            VALUES (%s,%s,%s,%s,%s,NOW())
        """, (
            user_id,
            "manual_credit",
            amount,
            reference_id,
            description
        ))

        conn.commit()

        return True

    except Exception as e:

        conn.rollback()
        raise e

    finally:

        cur.close()
        conn.close()


def debit_wallet(user_id, amount, reference_id, description):
    """
    Debit wallet balance
    """

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        # check balance
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as balance
            FROM wallet_ledger
            WHERE user_id = %s
        """, (user_id,))

        balance = cur.fetchone()["balance"]

        if balance < amount:
            raise Exception("Insufficient wallet balance")

        debit_amount = -abs(amount)

        cur.execute("""
            INSERT INTO wallet_ledger
            (user_id, transaction_type, amount, reference_id, description, created_at)
            VALUES (%s,%s,%s,%s,%s,NOW())
        """, (
            user_id,
            "withdrawal_debit",
            debit_amount,
            reference_id,
            description
        ))

        conn.commit()

        return True

    except Exception as e:

        conn.rollback()
        raise e

    finally:

        cur.close()
        conn.close()
