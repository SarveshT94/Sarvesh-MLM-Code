from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


# -----------------------------------
# Level 1 Team
# -----------------------------------
def get_level_1_team(user_id):
    if not user_id:
        return []

    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, referral_code, full_name, created_at
                FROM users
                WHERE sponsor_id = %s
            """, (user_id,))

            return cur.fetchall()

    except Exception as e:
        logger.error(f"Level 1 team error | user={user_id} | error={str(e)}")
        return []


# -----------------------------------
# Total Team Count (with safety)
# -----------------------------------
def get_total_team_count(user_id, max_depth=20):
    if not user_id:
        return 0

    try:
        with get_cursor() as cur:
            cur.execute("""
                WITH RECURSIVE downline AS (
                    SELECT id, sponsor_id, 1 AS level
                    FROM users
                    WHERE sponsor_id = %s

                    UNION ALL

                    SELECT u.id, u.sponsor_id, d.level + 1
                    FROM users u
                    INNER JOIN downline d
                    ON u.sponsor_id = d.id
                    WHERE d.level < %s
                )
                SELECT COUNT(*) as count FROM downline
            """, (user_id, max_depth))

            result = cur.fetchone()
            return result["count"]

    except Exception as e:
        logger.error(f"Team count error | user={user_id} | error={str(e)}")
        return 0


# -----------------------------------
# Team by Specific Level
# -----------------------------------
def get_team_by_level(user_id, level):
    if not user_id or not level or level <= 0:
        return []

    try:
        with get_cursor() as cur:
            cur.execute("""
                WITH RECURSIVE downline AS (
                    SELECT id, sponsor_id, 1 AS lvl
                    FROM users
                    WHERE sponsor_id = %s

                    UNION ALL

                    SELECT u.id, u.sponsor_id, d.lvl + 1
                    FROM users u
                    INNER JOIN downline d
                    ON u.sponsor_id = d.id
                )
                SELECT id
                FROM downline
                WHERE lvl = %s
            """, (user_id, level))

            return cur.fetchall()

    except Exception as e:
        logger.error(f"Team by level error | user={user_id} | level={level} | error={str(e)}")
        return []


# -----------------------------------
# Full Genealogy Tree (Controlled)
# -----------------------------------
def get_genealogy_tree(user_id, max_depth=10):
    if not user_id:
        return []

    try:
        with get_cursor() as cur:
            cur.execute("""
                WITH RECURSIVE downline AS (
                    SELECT id, sponsor_id, referral_code, full_name, created_at, 1 AS level
                    FROM users
                    WHERE sponsor_id = %s

                    UNION ALL

                    SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.created_at, d.level + 1
                    FROM users u
                    INNER JOIN downline d
                    ON u.sponsor_id = d.id
                    WHERE d.level < %s
                )
                SELECT id, sponsor_id, referral_code, full_name, created_at, level
                FROM downline
                ORDER BY level
            """, (user_id, max_depth))

            return cur.fetchall()

    except Exception as e:
        logger.error(f"Genealogy tree error | user={user_id} | error={str(e)}")
        return []
