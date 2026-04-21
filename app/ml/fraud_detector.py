from app.db import get_cursor
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def calculate_user_risk_score(user_id):
    """
    Smart risk scoring system
    """

    score = 0
    reasons = []

    if not user_id:
        return {
            "user_id": user_id,
            "risk_score": 0,
            "risk_level": "low",
            "reasons": []
        }

    try:
        with get_cursor() as cur:

            # 1. Withdraw frequency
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM withdraw_requests
                WHERE user_id = %s
                AND requested_at > NOW() - INTERVAL '7 days'
            """, (user_id,))
            withdraw_count = cur.fetchone()["cnt"]

            if withdraw_count > 5:
                score += 25
                reasons.append("High withdraw frequency")

            # 2. Wallet spike (FIXED INDENT)
            cur.execute("""
                SELECT COALESCE(SUM(amount),0) as total
                FROM wallet_ledger
                WHERE user_id = %s
                AND created_at > NOW() - INTERVAL '1 day'
            """, (user_id,))
            daily_volume = Decimal(str(cur.fetchone()["total"]))

            if daily_volume > Decimal("50000"):
                score += 30
                reasons.append("Unusual wallet activity spike")

            # 3. Referral explosion
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM users
                WHERE sponsor_id = %s
                AND created_at > NOW() - INTERVAL '1 day'
            """, (user_id,))
            referrals = cur.fetchone()["cnt"]

            if referrals > 10:
                score += 20
                reasons.append("Abnormal referral growth")

            # 4. Circular referral
            cur.execute("""
                SELECT u1.id
                FROM users u1
                JOIN users u2 ON u1.sponsor_id = u2.id
                WHERE u2.sponsor_id = u1.id
                AND u1.id = %s
            """, (user_id,))

            if cur.fetchone():
                score += 40
                reasons.append("Circular referral detected")

            # 5. Rejected withdraw pattern (FIXED INDENT)
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM withdraw_requests
                WHERE user_id = %s
                AND status = 'rejected'
            """, (user_id,))
            rejected = cur.fetchone()["cnt"]

            if rejected > 3:
                score += 15
                reasons.append("Multiple rejected withdrawals")

        return {
            "user_id": user_id,
            "risk_score": min(score, 100),
            "risk_level": _get_risk_level(score),
            "reasons": reasons
        }

    except Exception as e:
        logger.error(f"Risk calculation failed | user={user_id} | error={str(e)}")

        return {
            "user_id": user_id,
            "risk_score": 0,
            "risk_level": "unknown",
            "reasons": []
        }


def _get_risk_level(score):
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"
