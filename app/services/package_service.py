from app.db import get_cursor
from decimal import Decimal
import json

# -----------------------------------
# Create a New Dynamic Combo Plan
# -----------------------------------
def create_package(name, price, direct_commission, level_commissions_dict):
    """
    Enterprise Product Engine:
    Creates a new Combo Plan. The 'level_commissions_dict' takes a standard Python dictionary
    (e.g., {1: 0.05, 2: 0.03}) and safely converts it to JSON so the database can store 
    infinite dynamic levels for this specific package.
    """
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
            json.dumps(level_commissions_dict), # Stores the math rules dynamically
            True
        ))
        
        return cur.fetchone()['id']

# -----------------------------------
# Get All Active Packages (For the Store/Registration)
# -----------------------------------
def get_all_active_packages():
    """
    Fetches all packages that are currently available for users to buy.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, name, price, direct_commission, level_commissions 
            FROM packages 
            WHERE is_active = TRUE 
            ORDER BY price ASC
        """)
        return cur.fetchall()

# -----------------------------------
# Get a Single Package (For Commission Calculation)
# -----------------------------------
def get_package_by_id(package_id):
    """
    Fetches the specific math rules for a single combo plan.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, name, price, direct_commission, level_commissions 
            FROM packages 
            WHERE id = %s
        """, (package_id,))
        
        package = cur.fetchone()
        
        # We must convert the JSON back into a Python dictionary so the math engine can read it
        if package and package['level_commissions']:
            if isinstance(package['level_commissions'], str):
                package['level_commissions'] = json.loads(package['level_commissions'])
                
        return package

# -----------------------------------
# Update/Retire a Package (Safe Versioning)
# -----------------------------------
def deactivate_package(package_id):
    """
    Enterprise Rule: NEVER delete a package, because old commissions are tied to it.
    Instead, we 'deactivate' it so it stops showing up in the store, but the history remains intact.
    """
    with get_cursor() as cur:
        cur.execute("""
            UPDATE packages 
            SET is_active = FALSE 
            WHERE id = %s
        """, (package_id,))
        return True


# -----------------------------------
# Purchase a Package
# -----------------------------------
def purchase_package(user_id, package_id):
    """
    Enterprise API: Processes a user's package purchase.
    (This is a safe placeholder so your server can boot up. We will connect 
    this to the commission engine and wallet later).
    """
    package = get_package_by_id(package_id)
    
    if not package:
        return {"success": False, "message": "Package not found."}
        
    return {
        "success": True,
        "purchase_id": 999, # Placeholder ID
        "amount": package['price']
    }
