from app.db import get_cursor
from app.services.commission_service import distribute_commission


def activate_user(user_id, purchase_amount, force_commission=False):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT id, is_active
            FROM users
            WHERE id = %s
        """, (user_id,))

        user = cur.fetchone()

        if not user:
            raise Exception("User not found")

        # Activate if not active
        if not user["is_active"]:
            cur.execute("""
                UPDATE users
                SET is_active = TRUE,
                    activated_at = NOW()
                WHERE id = %s
            """, (user_id,))

        # Run commission
        if (not user["is_active"]) or force_commission:
            distribute_commission(conn, cur, user_id, purchase_amount)

        conn.commit()

        return {
            "success": True,
            "message": "Activation and commission processed"
        }

    except Exception as e:

        conn.rollback()

        return {
            "success": False,
            "message": str(e)
        }

    finally:

        cur.close()
        conn.close()
