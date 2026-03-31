from app.db import get_db_connection


def get_income_summary(user_id):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        # TOTAL COMMISSION
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as total_income
            FROM commissions
            WHERE earner_id=%s
        """, (user_id,))

        total_income = cur.fetchone()["total_income"]

        # TODAY INCOME
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as today_income
            FROM commissions
            WHERE earner_id=%s
            AND DATE(created_at) = CURRENT_DATE
        """, (user_id,))

        today_income = cur.fetchone()["today_income"]

        # WALLET BALANCE
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) as wallet_balance
            FROM wallet_ledger
            WHERE user_id=%s
        """, (user_id,))

        wallet_balance = cur.fetchone()["wallet_balance"]

        return {
            "total_income": total_income,
            "today_income": today_income,
            "wallet_balance": wallet_balance
        }

    finally:

        cur.close()
        conn.close()
