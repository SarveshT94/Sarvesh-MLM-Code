from app.db import get_cursor
from decimal import Decimal
import json


# -----------------------------------
# Create a New Dynamic Combo Plan
# -----------------------------------
def create_package(name, price, direct_commission, level_commissions_dict):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO packages
            (name, price, direct_commission, level_commissions, is_active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            name,
            Decimal(str(price)),
            Decimal(str(direct_commission)),
            json.dumps(level_commissions_dict),
            True
        ))
        
        return cur.fetchone()['id']


# -----------------------------------
# Get All Active Packages
# -----------------------------------
def get_all_active_packages():
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, name, price, direct_commission, level_commissions 
            FROM packages 
            WHERE is_active = TRUE 
            ORDER BY price ASC
        """)
        return cur.fetchall()


# -----------------------------------
# Get a Single Package
# -----------------------------------
def get_package_by_id(package_id, cur=None):
    """
    Supports both:
    - standalone calls (creates cursor)
    - transactional calls (uses existing cursor)
    """

    if cur:
        cur.execute("""
            SELECT id, name, price, direct_commission, level_commissions 
            FROM packages 
            WHERE id = %s
        """, (package_id,))
        
        package = cur.fetchone()

    else:
        with get_cursor() as new_cur:
            new_cur.execute("""
                SELECT id, name, price, direct_commission, level_commissions 
                FROM packages 
                WHERE id = %s
            """, (package_id,))
            
            package = new_cur.fetchone()

    # Convert JSON → dict
    if package and package['level_commissions']:
        if isinstance(package['level_commissions'], str):
            package['level_commissions'] = json.loads(package['level_commissions'])

    return package


# -----------------------------------
# Deactivate Package
# -----------------------------------
def deactivate_package(package_id):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE packages 
            SET is_active = FALSE 
            WHERE id = %s
        """, (package_id,))
        return True


# -----------------------------------
# Activate User Package (🔥 NEW - CRITICAL)
# -----------------------------------
def activate_user_package(cur, user_id, package_id):
    """
    Enterprise-safe activation inside existing transaction.
    """

    # ✅ Get package using SAME transaction
    package = get_package_by_id(package_id, cur)

    if not package:
        raise Exception("Package not found")

    # ---------------------------
    # Example Activation Logic
    # ---------------------------
    # (Keep minimal — extend later if needed)

    cur.execute("""
        UPDATE users
        SET package_id = %s,
            is_active = TRUE,
            activated_at = NOW()
        WHERE id = %s
    """, (package_id, user_id))

    # ---------------------------
    # Optional: Track purchase
    # ---------------------------
    cur.execute("""
        INSERT INTO user_packages
        (user_id, package_id, amount, created_at)
        VALUES (%s, %s, %s, NOW())
    """, (
        user_id,
        package_id,
        package['price']
    ))

    return True


# -----------------------------------
# Purchase Package (Standalone API)
# -----------------------------------
def purchase_package(user_id, package_id):
    """
    Standalone purchase flow (non E-PIN).
    """

    try:
        with get_cursor() as cur:

            package = get_package_by_id(package_id, cur)

            if not package:
                return {"success": False, "message": "Package not found."}

            activate_user_package(cur, user_id, package_id)

            return {
                "success": True,
                "amount": package['price']
            }

    except Exception as e:
        return {"success": False, "message": str(e)}
