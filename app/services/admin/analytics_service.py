from app.db import get_cursor


def get_mlm_analytics():

    cursor = get_cursor()

    data = {}

    # --------------------------------
    # Daily Registrations
    # --------------------------------
    cursor.execute("""
        SELECT DATE(created_at) AS date,
               COUNT(*) AS registrations
        FROM users
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 7
    """)

    data["daily_registrations"] = cursor.fetchall()

    # --------------------------------
    # Top Sponsors
    # --------------------------------
    cursor.execute("""
        SELECT sponsor_id,
               COUNT(*) AS referrals
        FROM users
        WHERE sponsor_id IS NOT NULL
        GROUP BY sponsor_id
        ORDER BY referrals DESC
        LIMIT 5
    """)

    data["top_sponsors"] = cursor.fetchall()

    # --------------------------------
    # Top Earners
    # --------------------------------
    cursor.execute("""
        SELECT user_id,
               SUM(amount) AS total_income
        FROM commission_logs
        GROUP BY user_id
        ORDER BY total_income DESC
        LIMIT 5
    """)

    data["top_earners"] = cursor.fetchall()

    # --------------------------------
    # Package Sales Summary
    # --------------------------------
    cursor.execute("""
        SELECT package_id,
               COUNT(*) AS total_sales
        FROM package_purchases
        GROUP BY package_id
    """)

    data["package_sales"] = cursor.fetchall()

    # --------------------------------
    # Commission Distribution
    # --------------------------------
    cursor.execute("""
        SELECT level,
               SUM(amount) AS total_commission
        FROM commission_logs
        GROUP BY level
        ORDER BY level
    """)

    data["commission_distribution"] = cursor.fetchall()

    return data
