from app.db import get_cursor
from app.utils.epin_generator import generate_epin
from app.services.package_service import activate_user_package


def generate_epins(admin_id, package_id, amount, quantity):
    """
    Generate multiple E-Pins.
    """

    pins = []

    try:
        with get_cursor() as cur:

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

        # ✅ Auto commit

        return {
            "success": True,
            "pins": pins
        }

    except Exception as e:
        # ✅ Auto rollback
        raise e


def redeem_epin(user_id, pin_code):
    """
    Redeem an E-Pin and activate package.
    """

    try:
        with get_cursor() as cur:

            # ✅ Validate E-Pin
            cur.execute("""
                SELECT *
                FROM epins
                WHERE pin_code = %s
                AND status = 'unused'
            """, (pin_code,))

            pin = cur.fetchone()

            if not pin:
                return {
                    "success": False,
                    "message": "Invalid or used E-Pin"
                }

            package_id = pin["package_id"]

            # ⚠️ IMPORTANT: pass cur for transaction consistency
            activate_user_package(cur, user_id, package_id)

            # ✅ Mark pin as used
            cur.execute("""
                UPDATE epins
                SET status = 'used',
                    used_by = %s,
                    used_at = NOW()
                WHERE id = %s
            """, (user_id, pin["id"]))

        # ✅ Auto commit

        return {
            "success": True,
            "message": "Package activated successfully"
        }

    except Exception as e:
        # ✅ Auto rollback
        raise e
