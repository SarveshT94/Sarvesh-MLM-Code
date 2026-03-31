from app.db import get_db_connection
from app.services.commission_service import distribute_commission


def purchase_package(user_id, package_id):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        # -------------------------------
        # Fetch package
        # -------------------------------

        cur.execute("""
            SELECT id, price, name
            FROM packages
            WHERE id = %s
        """, (package_id,))

        package = cur.fetchone()

        if not package:
            return {
                "success": False,
                "message": "Invalid package"
            }

        amount = package["price"]

        # -------------------------------
        # Prevent duplicate purchase
        # -------------------------------

        cur.execute("""
            SELECT id
            FROM user_packages
            WHERE user_id = %s
            AND package_id = %s
        """, (user_id, package_id))

        existing = cur.fetchone()

        if existing:
            return {
                "success": False,
                "message": "Package already purchased"
            }

        # -------------------------------
        # Insert purchase
        # -------------------------------

        cur.execute("""
            INSERT INTO user_packages
            (user_id, package_id, amount, purchased_at)
            VALUES (%s,%s,%s,NOW())
            RETURNING id
        """, (
            user_id,
            package_id,
            amount
        ))

        purchase = cur.fetchone()

        purchase_id = purchase["id"]

        # -------------------------------
        # Activate user
        # -------------------------------

        cur.execute("""
            UPDATE users
            SET is_active = TRUE
            WHERE id = %s
        """, (user_id,))

        # -------------------------------
        # Trigger MLM commission
        # -------------------------------

        distribute_commission(
            conn,
            cur,
            user_id,
            amount
        )

        # -------------------------------
        # Commit transaction
        # -------------------------------

        conn.commit()

        return {
            "success": True,
            "purchase_id": purchase_id,
            "amount": amount
        }

    except Exception as e:

        conn.rollback()
        raise e

    finally:

        cur.close()
        conn.close()



def activate_user_package(user_id, package_id):
    return {"status": "pending", "message": "Logic not implemented yet"}
