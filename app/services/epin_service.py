from app.db import get_db_connection
from app.utils.epin_generator import generate_epin
from app.services.package_service import activate_user_package

def generate_epins(admin_id, package_id, amount, quantity):

    conn = get_db_connection()
    cur = conn.cursor()

    pins = []

    try:

        for _ in range(quantity):

            pin = generate_epin()

            cur.execute("""
                INSERT INTO epins
                (pin_code, package_id, amount, created_by)
                VALUES (%s,%s,%s,%s)
                RETURNING pin_code
            """, (
                pin,
                package_id,
                amount,
                admin_id
            ))

            pins.append(cur.fetchone()["pin_code"])

        conn.commit()

        return {
            "success": True,
            "pins": pins
        }

    except Exception as e:

        conn.rollback()
        raise e

    finally:

        cur.close()
        conn.close()


def redeem_epin(user_id, pin_code):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT *
            FROM epins
            WHERE pin_code=%s
            AND status='unused'
        """, (pin_code,))

        pin = cur.fetchone()

        if not pin:

            return {
                "success": False,
                "message": "Invalid or used E-Pin"
            }

        package_id = pin["package_id"]

        # activate package
        activate_user_package(user_id, package_id)

        cur.execute("""
            UPDATE epins
            SET status='used',
                used_by=%s,
                used_at=NOW()
            WHERE id=%s
        """, (user_id, pin["id"]))

        conn.commit()

        return {
            "success": True,
            "message": "Package activated successfully"
        }

    except Exception as e:

        conn.rollback()
        raise e

    finally:

        cur.close()
        conn.close()
