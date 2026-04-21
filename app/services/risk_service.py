from app.db import get_cursor
import logging
from app.ml.fraud_detector import calculate_user_risk_score

logger = logging.getLogger(__name__)


# =========================================================
# FETCH USERS WITH BASIC INFO
# =========================================================
def get_all_users_for_risk():
    """
    Fetch users with financial + behavior signals
    """
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT 
                    u.id,
                    u.full_name,
                    u.email,
                    u.is_active,

                    COALESCE(SUM(CASE 
                        WHEN wl.transaction_type LIKE '%credit%' 
                        THEN wl.amount ELSE 0 END),0) as total_earnings,

                    COALESCE(SUM(CASE 
                        WHEN wl.transaction_type LIKE '%debit%' 
                        THEN wl.amount ELSE 0 END),0) as total_withdrawn,

                    COUNT(wr.id) as withdraw_count

                FROM users u
                LEFT JOIN wallet_ledger wl ON wl.user_id = u.id
                LEFT JOIN withdraw_requests wr ON wr.user_id = u.id

                GROUP BY u.id
                ORDER BY u.id DESC
                LIMIT 200
            """)

            return cur.fetchall()

    except Exception as e:
        logger.error(f"Risk fetch error: {str(e)}")
        return []


# =========================================================
# RISK DASHBOARD
# =========================================================
def get_risk_dashboard():
    """
    Returns risk analysis for dashboard
    """
    users = get_all_users_for_risk()
    result = []

    for user in users:
        try:
            risk = calculate_user_risk_score(user["id"])

            result.append({
                "id": user["id"],
                "name": user["full_name"],
                "email": user["email"],
                "is_active": user["is_active"],
                "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"],
                "reasons": risk["reasons"]
            })

        except Exception as e:
            logger.error(f"Risk calc failed for user {user['id']}: {str(e)}")
            continue

    return result


# =========================================================
# RISK SUMMARY (NEW - FOR DASHBOARD CARDS)
# =========================================================
def get_risk_summary(risk_data):
    """
    Returns aggregated counts for UI dashboard
    """
    summary = {
        "high": 0,
        "medium": 0,
        "low": 0
    }

    for user in risk_data:
        level = user.get("risk_level")

        if level == "high":
            summary["high"] += 1
        elif level == "medium":
            summary["medium"] += 1
        else:
            summary["low"] += 1

    return summary


# =========================================================
# BLOCK USER (NEW - REUSABLE)
# =========================================================
def block_user(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE users
                SET is_active = FALSE
                WHERE id = %s
                AND is_active = TRUE
            """, (user_id,))

            if cur.rowcount > 0:
                logger.warning(f"🔒 Admin blocked user {user_id}")
                return True

        return False

    except Exception as e:
        logger.error(f"Block user failed: {str(e)}")
        return False


# =========================================================
# UNBLOCK USER (NEW - REUSABLE)
# =========================================================
def unblock_user(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE users
                SET is_active = TRUE
                WHERE id = %s
                AND is_active = FALSE
            """, (user_id,))

            if cur.rowcount > 0:
                logger.info(f"✅ Admin unblocked user {user_id}")
                return True

        return False

    except Exception as e:
        logger.error(f"Unblock user failed: {str(e)}")
        return False


# =========================================================
# AUTO BLOCK SYSTEM (OPTIMIZED)
# =========================================================
def auto_block_high_risk_users():
    """
    Auto-disable risky users (enterprise protection)
    """
    try:
        users = get_risk_dashboard()

        with get_cursor() as cur:
            for user in users:

                if user["risk_level"] != "high":
                    continue

                cur.execute("""
                    UPDATE users
                    SET is_active = FALSE
                    WHERE id = %s
                    AND is_active = TRUE
                """, (user["id"],))

                if cur.rowcount > 0:
                    logger.warning(
                        f"🚨 AUTO BLOCKED USER {user['id']} "
                        f"(Risk={user['risk_score']})"
                    )

    except Exception as e:
        logger.error(f"Auto block failed: {str(e)}")
