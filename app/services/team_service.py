from app.db import get_cursor

def get_level_1_team(user_id):
    """
    Direct referrals (Level 1)
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, referral_code, full_name, created_at
            FROM users
            WHERE sponsor_id = %s
            """,
            (user_id,)
        )
        team = cur.fetchall()
    return team

def get_total_team_count(user_id):
    """
    Total downline count (all levels)
    """
    with get_cursor() as cur:
        cur.execute(
            """
            WITH RECURSIVE downline AS (
                SELECT id, sponsor_id
                FROM users
                WHERE sponsor_id = %s

                UNION ALL

                SELECT u.id, u.sponsor_id
                FROM users u
                INNER JOIN downline d
                ON u.sponsor_id = d.id
            )
            SELECT COUNT(*) as count FROM downline
            """,
            (user_id,)
        )
        result = cur.fetchone()
        count = result["count"]
        return count

def get_team_by_level(user_id, level):
    """
    Get team members by specific level
    """
    with get_cursor() as cur:
        cur.execute(
            """
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
            """,
            (user_id, level)
        )
        team = cur.fetchall()
    return team

def get_genealogy_tree(user_id):
    """
    Returns full MLM genealogy tree for a user
    """
    with get_cursor() as cur:
        cur.execute(
            """
            WITH RECURSIVE downline AS (
                -- Base Case: Add full_name and created_at
                SELECT id, sponsor_id, referral_code, full_name, created_at, 1 AS level
                FROM users
                WHERE sponsor_id = %s

                UNION ALL

                -- Recursive Case: Add u.full_name and u.created_at
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.created_at, d.level + 1
                FROM users u
                INNER JOIN downline d
                ON u.sponsor_id = d.id
            )
            -- Final Select: Pull the newly added columns
            SELECT id, sponsor_id, referral_code, full_name, created_at, level
            FROM downline
            ORDER BY level
            """,
            (user_id,)
        )
        rows = cur.fetchall()
    return rows
