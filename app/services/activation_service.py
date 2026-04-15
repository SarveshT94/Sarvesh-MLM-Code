from app.db import get_cursor
from app.services.commission_service import distribute_commission


def activate_user(user_id, purchase_amount, force_commission=False):
    """
    Activate user and optionally trigger commission distribution.
    """

    try:
        with get_cursor() as cur:

            # ✅ Fetch user
            cur.execute("""
                SELECT id, is_active
                FROM users
                WHERE id = %s
            """, (user_id,))

            user = cur.fetchone()

            if not user:
                raise Exception("User not found")

            # ✅ Activate if not active
            if not user["is_active"]:
                cur.execute("""
                    UPDATE users
                    SET is_active = TRUE,
                        activated_at = NOW()
                    WHERE id = %s
                """, (user_id,))

            # ✅ Run commission
            if (not user["is_active"]) or force_commission:
                distribute_commission(cur, user_id, purchase_amount)

        # ✅ Auto commit handled by get_cursor()

        return {
            "success": True,
            "message": "Activation and commission processed"
        }

    except Exception as e:
        # ✅ Auto rollback handled by get_cursor()

        return {
            "success": False,
            "message": str(e)
        }
