from app.db import get_cursor


def get_income_summary(user_id):
    """
    Fetch income summary for a user:
    - Total income
    - Today's income
    - Wallet balance
    """

    try:
        with get_cursor() as cur:

            # ---------------------------
            # TOTAL COMMISSION
            # ---------------------------
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS total_income
                FROM commissions
                WHERE earner_id = %s
            """, (user_id,))

            total_income = cur.fetchone()["total_income"]

            # ---------------------------
            # TODAY INCOME
            # ---------------------------
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS today_income
                FROM commissions
                WHERE earner_id = %s
                AND DATE(created_at) = CURRENT_DATE
            """, (user_id,))

            today_income = cur.fetchone()["today_income"]

            # ---------------------------
            # WALLET BALANCE
            # ---------------------------
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS wallet_balance
                FROM wallet_ledger
                WHERE user_id = %s
            """, (user_id,))

            wallet_balance = cur.fetchone()["wallet_balance"]

            return {
                "total_income": total_income,
                "today_income": today_income,
                "wallet_balance": wallet_balance
            }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
