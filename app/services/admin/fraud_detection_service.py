from app.db import get_cursor


def get_fraud_report():

    cursor = get_cursor()

    report = {}

    # ---------------------------------
    # Self Referral Detection
    # ---------------------------------
    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE sponsor_id = id
    """)

    report["self_referrals"] = cursor.fetchone()["count"]

    # ---------------------------------
    # Circular Sponsor Chains
    # ---------------------------------
    cursor.execute("""
        SELECT COUNT(*)
        FROM users u1
        JOIN users u2 ON u1.sponsor_id = u2.id
        WHERE u2.sponsor_id = u1.id
    """)

    report["circular_sponsors"] = cursor.fetchone()["count"]

    # ---------------------------------
    # Duplicate Emails
    # ---------------------------------
    cursor.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT email
            FROM users
            GROUP BY email
            HAVING COUNT(*) > 1
        ) duplicates
    """)

    report["duplicate_emails"] = cursor.fetchone()["count"]

    # ---------------------------------
    # Suspicious Commission Activity
    # Example: unusually high commissions
    # ---------------------------------
    cursor.execute("""
        SELECT COUNT(*)
        FROM commission_logs
        WHERE amount > 100000
    """)

    report["suspicious_commissions"] = cursor.fetchone()["count"]

    return report
