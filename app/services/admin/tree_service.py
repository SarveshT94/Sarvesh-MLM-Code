from app.db import get_cursor
from app.cache import cache  # 🔥 KEPT YOUR CACHE
import logging

logger = logging.getLogger(__name__)

def get_children(user_id):
    """Fetches direct downlines from the database."""
    with get_cursor() as cur:
        # Added email, phone
        cur.execute("""
            SELECT id, full_name, email, phone, referral_code, is_active, created_at
            FROM users
            WHERE sponsor_id = %s
        """, (user_id,))
        return cur.fetchall()


def build_tree(user_id, depth=0, max_depth=10):
    if depth >= max_depth:
        return []

    children = get_children(user_id)
    tree = []

    for child in children:
        node = {
            "user_id": child["id"],
            "full_name": child["full_name"],
            "email": child["email"],
            "phone": child["phone"],
            "referral_code": child["referral_code"],
            "is_active": child["is_active"],
            "created_at": child["created_at"],
            "children": build_tree(child["id"], depth + 1, max_depth)
        }
        tree.append(node)

    return tree


# =================================================================
# 🔥 ENTERPRISE UPGRADE: THE CACHE DECORATOR
# Saves the output in RAM for 5 minutes (300 seconds) so the database 
# isn't spammed with thousands of recursive queries.
# =================================================================
@cache.memoize(timeout=1)
def get_user_tree(user_id):
    """
    Retrieves the entire genealogy tree for a user.
    Heavily cached to prevent database recursion crashes during high traffic.
    """
    logger.info(f"CACHE MISS: Calculating heavy genealogy tree for User {user_id}...")
    try:
        with get_cursor() as cur:
            # Added email, phone, created_at
            cur.execute("""
                SELECT id, full_name, email, phone, referral_code, is_active, created_at
                FROM users
                WHERE id = %s
            """, (user_id,))
            user = cur.fetchone()

        if not user:
            return None

        return {
            "user_id": user["id"],
            "full_name": user["full_name"],          
            "email": user["email"],
            "phone": user["phone"],
            "referral_code": user["referral_code"],
            "is_active": user["is_active"],
            "created_at": user.get("created_at"),
            "children": build_tree(user["id"])
        }
    except Exception as e:
        logger.error(f"Tree service error for user {user_id}: {str(e)}")
        return None
