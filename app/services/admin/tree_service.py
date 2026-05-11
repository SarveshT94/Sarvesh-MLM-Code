from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def get_children(user_id):
    """
    BUG FIXED #3:
    - Was using cursor = get_cursor() directly (crashes).
    - Was selecting 'username' column which doesn't exist. Correct column = 'full_name'.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, full_name, referral_code, is_active, created_at
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
            "full_name": child["full_name"],        # FIXED: was 'username'
            "referral_code": child["referral_code"],
            "is_active": child["is_active"],
            "children": build_tree(child["id"], depth + 1, max_depth)
        }
        tree.append(node)

    return tree


def get_user_tree(user_id):
    """
    BUG FIXED #3: was using cursor = get_cursor() directly.
    """
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, full_name, referral_code, is_active
                FROM users
                WHERE id = %s
            """, (user_id,))
            user = cur.fetchone()

        if not user:
            return None

        return {
            "user_id": user["id"],
            "full_name": user["full_name"],          # FIXED: was 'username'
            "referral_code": user["referral_code"],
            "is_active": user["is_active"],
            "children": build_tree(user["id"])
        }
    except Exception as e:
        logger.error(f"Tree service error for user {user_id}: {str(e)}")
        return None
