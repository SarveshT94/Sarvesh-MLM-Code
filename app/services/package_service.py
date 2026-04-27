from app.db import get_cursor
from decimal import Decimal
from app.services.commission_log_service import distribute_package_commissions

# ==========================================
# 1. SUBSCRIPTION PLANS MANAGEMENT
# ==========================================
def get_all_plans():
    """Fetches all plans and their associated product images."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM subscription_plans ORDER BY price ASC")
            plans = cur.fetchall()

            # Fetch the dynamic images for each plan
            for plan in plans:
                cur.execute("SELECT image_path FROM plan_images WHERE plan_id = %s", (plan['id'],))
                images = cur.fetchall()
                # Attach an array of image paths to the plan object
                plan['images'] = [img['image_path'] for img in images]
                
            return plans
    except Exception as e:
        print(f"Error fetching plans: {str(e)}")
        return []

def add_plan_image(plan_id, image_path):
    """Saves a new uploaded image path to the database."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO plan_images (plan_id, image_path) VALUES (%s, %s)", 
                (plan_id, image_path)
            )
    except Exception as e:
        print(f"Error saving image path: {str(e)}")


def get_plan_by_id(plan_id, cur=None):
    """
    Supports both standalone calls and transactional calls.
    """
    query = "SELECT * FROM subscription_plans WHERE id = %s"
    
    if cur:
        cur.execute(query, (plan_id,))
        return cur.fetchone()
    else:
        with get_cursor() as new_cur:
            new_cur.execute(query, (plan_id,))
            return new_cur.fetchone()

# Backward compatibility alias so other files don't break
get_package_by_id = get_plan_by_id
get_all_active_packages = get_all_plans


def update_plan(plan_id, price, coupons, is_active):
    """Updates plan dynamically from Admin Dashboard"""
    with get_cursor() as cur:
        cur.execute("""
            UPDATE subscription_plans 
            SET price = %s, lucky_draw_coupons = %s, is_active = %s
            WHERE id = %s
        """, (price, coupons, is_active, plan_id))

def create_plan(name, price, coupons=12):
    """Creates a new plan"""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO subscription_plans (name, price, lucky_draw_coupons, is_active)
            VALUES (%s, %s, %s, TRUE) RETURNING id
        """, (name, price, coupons))
        return cur.fetchone()['id']


# ==========================================
# 2. GLOBAL & LEVEL COMMISSIONS MANAGEMENT
# ==========================================
def get_global_commissions():
    """Fetches flat percentages like direct referral and cashback"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM global_commissions ORDER BY setting_key")
        return cur.fetchall()

def update_global_commission(setting_key, percentage_value):
    """Updates a global percentage dynamically from Admin Dashboard"""
    with get_cursor() as cur:
        cur.execute("""
            UPDATE global_commissions 
            SET percentage_value = %s
            WHERE setting_key = %s
        """, (percentage_value, setting_key))

def get_level_commissions():
    """Fetches the 10-level upline percentages"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM level_commissions ORDER BY level ASC")
        return cur.fetchall()

def get_team_target_bonuses():
    """Fetches the performance bonuses"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM team_target_bonuses ORDER BY min_volume ASC")
        return cur.fetchall()


# ==========================================
# 3. USER ACTIVATION & PURCHASE FLOW
# ==========================================
def activate_user_package(cur, user_id, plan_id):
    """
    Enterprise-safe activation inside existing transaction.
    """
    plan = get_plan_by_id(plan_id, cur)

    if not plan:
        raise Exception("Plan not found")

    # Update User Profile
    cur.execute("""
        UPDATE users
        SET package_id = %s,
            is_active = TRUE,
            activated_at = NOW()
        WHERE id = %s
    """, (plan_id, user_id))

    # Track purchase in history
    cur.execute("""
        INSERT INTO user_packages
        (user_id, package_id, amount, created_at)
        VALUES (%s, %s, %s, NOW())
    """, (
        user_id,
        plan_id,
        plan['price']
    ))

    return True

def purchase_package(user_id, plan_id):
    """
    Standalone purchase flow.
    """
    try:
        with get_cursor() as cur:
            plan = get_plan_by_id(plan_id, cur)

            if not plan:
                return {"success": False, "message": "Plan not found."}

            # 1. Activate the user and record the purchase
            activate_user_package(cur, user_id, plan_id)
            
            # 2. 🔥 THE MAGIC TRIGGER: Distribute the 10-level commissions & Target Bonus!
            distribute_package_commissions(cur, user_id, plan['price'])

            return {
                "success": True,
                "amount": plan['price']
            }

    except Exception as e:
        return {"success": False, "message": str(e)}
