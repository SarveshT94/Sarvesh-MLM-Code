# app/services/package_service.py
from app.db import get_cursor
from decimal import Decimal

# ==========================================
# 1. SUBSCRIPTION PLANS MANAGEMENT
# ==========================================
def get_all_plans():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM subscription_plans ORDER BY price ASC")
            plans = cur.fetchall()
            for plan in plans:
                cur.execute("SELECT image_path FROM plan_images WHERE plan_id = %s", (plan['id'],))
                images = cur.fetchall()
                plan['images'] = [img['image_path'] for img in images]
            return plans
    except Exception as e:
        print(f"Error fetching plans: {str(e)}")
        return []

def add_plan_image(plan_id, image_path):
    try:
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO plan_images (plan_id, image_path) VALUES (%s, %s)",
                (plan_id, image_path)
            )
    except Exception as e:
        print(f"Error saving image path: {str(e)}")

def get_plan_by_id(plan_id, cur=None):
    query = "SELECT * FROM subscription_plans WHERE id = %s"
    if cur:
        cur.execute(query, (plan_id,))
        return cur.fetchone()
    else:
        with get_cursor() as new_cur:
            new_cur.execute(query, (plan_id,))
            return new_cur.fetchone()

get_package_by_id = get_plan_by_id
get_all_active_packages = get_all_plans

# ✅ NEW: Added product_cost parameter to update_plan
def update_plan(plan_id, price, coupons, is_active, product_cost=0):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE subscription_plans
            SET price = %s, lucky_draw_coupons = %s, product_cost = %s, is_active = %s
            WHERE id = %s
        """, (price, coupons, product_cost, is_active, plan_id))

# ✅ NEW: Added product_cost parameter to create_plan
def create_plan(name, price, coupons=12, product_cost=0):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO subscription_plans (name, price, lucky_draw_coupons, product_cost, is_active)
            VALUES (%s, %s, %s, %s, TRUE) RETURNING id
        """, (name, price, coupons, product_cost))
        return cur.fetchone()['id']

# ==========================================
# 2. GLOBAL & LEVEL COMMISSIONS MANAGEMENT
# ==========================================
def get_global_commissions():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM global_commissions ORDER BY setting_key")
        return cur.fetchall()

def update_global_commission(setting_key, percentage_value):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE global_commissions
            SET percentage_value = %s
            WHERE setting_key = %s
        """, (percentage_value, setting_key))

def get_level_commissions():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM level_commissions ORDER BY level ASC")
        return cur.fetchall()

# ==========================================
# 3. USER ACTIVATION & PURCHASE FLOW
# ==========================================
def activate_user_package(cur, user_id, plan_id):
    plan = get_plan_by_id(plan_id, cur)
    if not plan:
        raise Exception("Plan not found")
    
    cur.execute("""
        UPDATE users 
        SET package_id = %s, is_active = TRUE, activated_at = NOW()
        WHERE id = %s
    """, (plan_id, user_id))
    
    cur.execute("""
        INSERT INTO user_packages (user_id, package_id, amount, created_at)
        VALUES (%s, %s, %s, NOW())
    """, (user_id, plan_id, plan['price']))
    return True

def purchase_package(user_id, plan_id):
    """Main purchase function - Now correctly uses latest commissions"""
    try:
        with get_cursor() as cur:
            plan = get_plan_by_id(plan_id, cur)
            if not plan:
                return {"success": False, "message": "Plan not found."}

            activate_user_package(cur, user_id, plan_id)
            
            # Use new engine
            from app.services.commission_engine import distribute_commission
            result = distribute_commission(user_id, plan_id)
            
            if result.get("status") == "error":
                return {"success": False, "message": result.get("message", "Commission error")}
            
            return {
                "success": True,
                "amount": plan['price'],
                "message": "Package purchased successfully with updated commissions"
            }
    except Exception as e:
        print(f"Purchase error: {str(e)}")
        return {"success": False, "message": str(e)}

# ==========================================
# 4. COMMISSION HELPER
# ==========================================
def get_plan_with_commissions(plan_id):
    """Critical function - Loads latest commission percentages"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM subscription_plans WHERE id = %s", (plan_id,))
        plan = cur.fetchone()
        if not plan:
            return None

        # Load Level Commissions (This is what you change in admin)
        cur.execute("SELECT level, percentage FROM level_commissions ORDER BY level")
        levels = cur.fetchall()
        plan['level_commissions'] = {str(row['level']): row['percentage'] for row in levels}

        # Load Global Commissions (Direct Commission etc.)
        cur.execute("SELECT setting_key, percentage_value FROM global_commissions")
        for row in cur.fetchall():
            if row['setting_key'] == 'direct_commission':
                plan['direct_commission'] = row['percentage_value']

        return plan
