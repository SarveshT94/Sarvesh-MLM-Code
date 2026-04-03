from app.db import get_cursor
from app.services.sponsor_service import get_sponsor_chain
from app.services.package_service import get_package_by_id
from decimal import Decimal

def distribute_commission(buyer_id, package_id):
    """
    Enterprise Dynamic Commission Engine
    Reads the math rules directly from the specific purchased package.
    Handles both direct (flat) bonuses and dynamic percentage-based level commissions.
    """
    # 1. Load the specific package rules from the database
    package = get_package_by_id(package_id)
    if not package:
        return {"status": "error", "message": "Package not found or inactive."}
        
    purchase_amount = Decimal(str(package['price']))
    direct_bonus = Decimal(str(package['direct_commission']))
    level_rules = package['level_commissions'] or {} # E.g., {"1": 0.05, "2": 0.03}
    
    # 2. Get the optimized upline chain
    sponsors = get_sponsor_chain(buyer_id)

    # 3. Open safe database transaction
    with get_cursor() as cur:
        for level, sponsor_id in enumerate(sponsors, start=1):
            
            # JSON keys in the database are stored as strings, so we convert the integer level
            str_level = str(level)
            
            # A. Calculate Level Percentage Commission (if defined for this level)
            level_commission = Decimal('0')
            if str_level in level_rules:
                percent = Decimal(str(level_rules[str_level]))
                level_commission = (purchase_amount * percent).quantize(Decimal('0.01'))
                
            # B. Calculate Direct Bonus (This only goes to the exact person who invited them = Level 1)
            total_commission = level_commission
            if level == 1 and direct_bonus > 0:
                total_commission += direct_bonus
                
            # If no money is owed to this level (e.g., they hit the max depth), skip the database inserts
            if total_commission <= 0:
                continue

            # 4. Duplicate Protection (Idempotency check)
            cur.execute("""
                SELECT id
                FROM commissions
                WHERE earner_id = %s
                AND from_user_id = %s
                AND level = %s
            """, (sponsor_id, buyer_id, level))

            if cur.fetchone():
                continue

            # 5. Insert Permanent Commission Log
            cur.execute("""
                INSERT INTO commissions
                (earner_id, from_user_id, level, amount, commission_type)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                sponsor_id,
                buyer_id,
                level,
                total_commission,
                f"Combo Plan: {package['name']}"
            ))

            # 6. Wallet Credit (Double-Entry Ledger)
            cur.execute("""
                INSERT INTO wallet_ledger
                (user_id, amount, transaction_type, reference)
                VALUES (%s,%s,%s,%s)
            """, (
                sponsor_id,
                total_commission,
                "commission_credit",
                f"Level {level} bonus from {package['name']} purchase by user {buyer_id}"
            ))

    return {"status": "success", "message": "Commissions distributed seamlessly."}
