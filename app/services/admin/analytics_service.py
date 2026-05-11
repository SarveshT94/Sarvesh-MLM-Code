from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def get_mlm_analytics():
    """
    BUG FIXED #1 / #28:
    - Was calling cursor = get_cursor() directly — get_cursor() is a @contextmanager,
      not a cursor. Calling .execute() on it crashes immediately.
    - Was querying 'commission_logs' (doesn't exist) → fixed to 'commissions'
    - Was querying 'package_purchases' (doesn't exist) → fixed to 'user_packages'
    All queries now use the correct `with get_cursor() as cur:` pattern.
    """
    data = {}

    try:
        with get_cursor() as cur:

            # Daily Registrations (last 7 days)
            cur.execute("""
                SELECT DATE(created_at) AS date,
                       COUNT(*) AS registrations
                FROM users
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 7
            """)
            data["daily_registrations"] = cur.fetchall()

            # Top Sponsors by referral count
            cur.execute("""
                SELECT
                    u.id AS sponsor_id,
                    u.full_name,
                    COUNT(r.id) AS referrals
                FROM users u
                JOIN users r ON r.sponsor_id = u.id
                GROUP BY u.id, u.full_name
                ORDER BY referrals DESC
                LIMIT 5
            """)
            data["top_sponsors"] = cur.fetchall()

            # Top Earners — FIXED: was querying commission_logs (doesn't exist)
            cur.execute("""
                SELECT
                    c.earner_id AS user_id,
                    u.full_name,
                    SUM(c.amount) AS total_income
                FROM commissions c
                JOIN users u ON u.id = c.earner_id
                GROUP BY c.earner_id, u.full_name
                ORDER BY total_income DESC
                LIMIT 5
            """)
            data["top_earners"] = cur.fetchall()

            # Package Sales Summary — FIXED: was querying package_purchases (doesn't exist)
            cur.execute("""
                SELECT
                    up.package_id,
                    sp.name AS package_name,
                    COUNT(*) AS total_sales,
                    SUM(up.amount) AS total_revenue
                FROM user_packages up
                JOIN subscription_plans sp ON sp.id = up.package_id
                GROUP BY up.package_id, sp.name
                ORDER BY total_sales DESC
            """)
            data["package_sales"] = cur.fetchall()

            # Commission Distribution by level — FIXED: was querying commission_logs
            cur.execute("""
                SELECT
                    level,
                    SUM(amount) AS total_commission,
                    COUNT(*) AS transaction_count
                FROM commissions
                GROUP BY level
                ORDER BY level
            """)
            data["commission_distribution"] = cur.fetchall()

            # Revenue trend (last 30 days)
            cur.execute("""
                SELECT
                    DATE(created_at) AS date,
                    SUM(amount) AS daily_revenue
                FROM user_packages
                WHERE created_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """)
            data["revenue_trend"] = cur.fetchall()

    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")

    return data
