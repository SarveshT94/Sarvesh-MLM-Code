from app.db import get_cursor
# BUG FIXED #9: was importing from app.services.commission_service which does NOT EXIST.
# The correct module is app.services.commission_log_service
from app.services.commission_log_service import distribute_package_commissions
import logging

logger = logging.getLogger(__name__)


def activate_user(user_id, purchase_amount, force_commission=False):
    """
    Activate user and optionally trigger commission distribution.

    BUG FIXED #9:
    Old import: from app.services.commission_service import distribute_commission
    The file commission_service.py does not exist anywhere in the project.
    This caused a ModuleNotFoundError on import, crashing the entire app.
    Fixed: import from commission_log_service which is the correct module.
    """
    try:
        with get_cursor() as cur:

            cur.execute("""
                SELECT id, is_active
                FROM users
                WHERE id = %s
            """, (user_id,))
            user = cur.fetchone()

            if not user:
                return {"success": False, "message": "User not found"}

            was_inactive = not user["is_active"]

            if was_inactive:
                cur.execute("""
                    UPDATE users
                    SET is_active = TRUE,
                        activated_at = NOW()
                    WHERE id = %s
                """, (user_id,))

            if was_inactive or force_commission:
                distribute_package_commissions(cur, user_id, purchase_amount)

        return {"success": True, "message": "Activation and commission processed"}

    except Exception as e:
        logger.error(f"Activation error for user {user_id}: {str(e)}")
        return {"success": False, "message": str(e)}
