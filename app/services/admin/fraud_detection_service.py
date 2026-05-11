from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def get_fraud_report():
    """
    BUG FIXED #2 / #27:
    - Was using cursor = get_cursor() directly (crashes — it's a context manager).
    - Was querying 'commission_logs' → fixed to 'commissions'.
    All queries now use the correct `with get_cursor() as cur:` pattern.
    """
    report = {}

    try:
        with get_cursor() as cur:

            # Self-referral detection
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM users
                WHERE sponsor_id = id
            """)
            report["self_referrals"] = int(cur.fetchone()["count"])

            # Circular sponsor chains
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM users u1
                JOIN users u2 ON u1.sponsor_id = u2.id
                WHERE u2.sponsor_id = u1.id
            """)
            report["circular_sponsors"] = int(cur.fetchone()["count"])

            # Duplicate emails
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM (
                    SELECT email
                    FROM users
                    GROUP BY email
                    HAVING COUNT(*) > 1
                ) duplicates
            """)
            report["duplicate_emails"] = int(cur.fetchone()["count"])

            # Suspicious commission activity — FIXED: was querying commission_logs
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM commissions
                WHERE amount > 100000
            """)
            report["suspicious_commissions"] = int(cur.fetchone()["count"])

            # Rapid withdrawal attempts (>3 in a day)
            cur.execute("""
                SELECT COUNT(DISTINCT user_id) AS count
                FROM (
                    SELECT user_id, COUNT(*) AS daily_count
                    FROM withdraw_requests
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY user_id
                    HAVING COUNT(*) > 3
                ) rapid
            """)
            report["rapid_withdrawals"] = int(cur.fetchone()["count"])

            # Users with high earnings but no KYC
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM users u
                WHERE u.kyc_status != 'approved'
                AND (
                    SELECT COALESCE(SUM(c.amount), 0)
                    FROM commissions c WHERE c.earner_id = u.id
                ) > 10000
            """)
            report["high_earners_no_kyc"] = int(cur.fetchone()["count"])

    except Exception as e:
        logger.error(f"Fraud report error: {str(e)}")
        report["error"] = str(e)

    return report
