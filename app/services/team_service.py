from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)

# IMPORTANT: `rank` is a reserved keyword in PostgreSQL (the built-in
# RANK() OVER(...) / RANK() WITHIN GROUP ordered-set aggregate). Every
# query below that selects the `rank` column MUST double-quote it as
# "rank", or Postgres tries to parse it as the aggregate function and
# throws: 'WITHIN GROUP is required for ordered-set aggregate rank'.
# That error was previously being swallowed by the try/except in each
# function below and silently returned as an empty list -- which is
# why team data looked "missing" even though the query itself was
# otherwise correct.

# Single source of truth for how deep "team" queries go.
# Was previously inconsistent (20 in get_total_team_count vs 10 in
# get_genealogy_tree), which meant the count shown to a user/admin
# could be larger than the actual tree rendered on screen -- this is
# very likely the root cause of "team exists but isn't visible".
DEFAULT_MAX_DEPTH = 20


# -----------------------------------
# 1. Level 1 Team (Directs)
# -----------------------------------
def get_level_1_team(user_id):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT
                    id, sponsor_id, referral_code, full_name,
                    email, phone, is_active, "rank", created_at
                FROM users
                WHERE sponsor_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            rows = cur.fetchall()
            return [dict(row) for row in rows] if rows else []
    except Exception as e:
        logger.error(f"Level 1 team error | user={user_id} | error={str(e)}")
        return []


# -----------------------------------
# 2. Total Team Count
# -----------------------------------
def get_total_team_count(user_id, max_depth=DEFAULT_MAX_DEPTH):
    if not user_id:
        return 0
    try:
        with get_cursor() as cur:
            cur.execute("""
                WITH RECURSIVE downline AS (
                    SELECT id, sponsor_id, 1 AS level FROM users WHERE sponsor_id = %s
                    UNION ALL
                    SELECT u.id, u.sponsor_id, d.level + 1 FROM users u
                    INNER JOIN downline d ON u.sponsor_id = d.id WHERE d.level < %s
                )
                SELECT COUNT(*) as count FROM downline
            """, (user_id, max_depth))
            result = cur.fetchone()
            return result["count"] if result else 0
    except Exception as e:
        logger.error(f"Team count error | user={user_id} | error={str(e)}")
        return 0


# -----------------------------------
# 3. Team by Specific Level
# -----------------------------------
def get_team_by_level(user_id, level):
    if not user_id or not level or level <= 0:
        return []
    try:
        with get_cursor() as cur:
            cur.execute("""
                WITH RECURSIVE downline AS (
                    SELECT id, sponsor_id, 1 AS lvl FROM users WHERE sponsor_id = %s
                    UNION ALL
                    SELECT u.id, u.sponsor_id, d.lvl + 1 FROM users u
                    INNER JOIN downline d ON u.sponsor_id = d.id
                )
                SELECT
                    u.id, u.sponsor_id, u.referral_code, u.full_name,
                    u.email, u.phone, u.is_active, u."rank", u.created_at
                FROM downline d
                JOIN users u ON d.id = u.id
                WHERE d.lvl = %s
            """, (user_id, level))
            rows = cur.fetchall()
            return [dict(row) for row in rows] if rows else []
    except Exception as e:
        logger.error(f"Team by level error | user={user_id} | error={str(e)}")
        return []


# -----------------------------------
# 4. Full Genealogy Tree (FLAT LIST FOR ADMIN)
# -----------------------------------
def get_genealogy_tree(user_id, max_depth=DEFAULT_MAX_DEPTH):
    """
    Returns a FLAT LIST of the given user's downline (root included),
    each row tagged with its `level` relative to the root (root = 0).

    FIX vs previous version:
    - Previously did `SELECT * FROM users` (the ENTIRE users table) on
      every single call, then walked it in Python with BFS. That is an
      O(total_users) query for every admin click, and it silently
      capped depth at 10 while get_total_team_count capped at 20 --
      so deep downline members were counted but never shown in the
      tree. Fixed by doing the depth-bounded traversal in SQL via a
      recursive CTE (same pattern as get_total_team_count /
      get_team_by_level) and only fetching the rows that are actually
      part of this user's subtree.
    """
    if not user_id:
        return []

    try:
        with get_cursor() as cur:
            cur.execute("""
                WITH RECURSIVE downline AS (
                    SELECT id, sponsor_id, 0 AS level
                    FROM users
                    WHERE id = %s

                    UNION ALL

                    SELECT u.id, u.sponsor_id, d.level + 1
                    FROM users u
                    INNER JOIN downline d ON u.sponsor_id = d.id
                    WHERE d.level < %s
                )
                SELECT
                    u.id, u.sponsor_id, u.referral_code, u.full_name,
                    u.email, u.phone, u.is_active, u."rank", u.created_at,
                    d.level
                FROM downline d
                JOIN users u ON u.id = d.id
                ORDER BY d.level ASC, u.created_at ASC
            """, (user_id, max_depth))
            rows = cur.fetchall()

            if not rows:
                return []

            flat_team_list = []
            for row in rows:
                node = dict(row)
                node["id"] = str(node["id"])
                node["sponsor_id"] = (
                    str(node["sponsor_id"]) if node.get("sponsor_id") else None
                )
                node["is_active"] = bool(node.get("is_active", True))
                node["rank"] = node.get("rank") or "Distributor"
                if node.get("created_at"):
                    node["created_at"] = str(node["created_at"])
                flat_team_list.append(node)

            return flat_team_list

    except Exception as e:
        logger.error(f"Genealogy tree error | user={user_id} | error={str(e)}")
        return []


# -----------------------------------
# 5. ADMIN DRILL-DOWN HELPERS
# -----------------------------------
def get_user_network_profile(user_id, max_depth=DEFAULT_MAX_DEPTH):
    """
    Upline + downline summary for a single user, used by the admin
    drill-down view.

    FIX vs previous version:
    - Previously opened THREE separate cursors/connections
      (get_total_team_count -> its own get_cursor(), get_level_1_team
      -> its own get_cursor(), plus the upline query on a fourth
      cursor that was opened but unused until the last query). Now
      reuses a single cursor for all three lookups.
    """
    if not user_id:
        return {}
    try:
        with get_cursor() as cur:
            cur.execute("""
                WITH RECURSIVE downline AS (
                    SELECT id, sponsor_id, 1 AS level FROM users WHERE sponsor_id = %s
                    UNION ALL
                    SELECT u.id, u.sponsor_id, d.level + 1 FROM users u
                    INNER JOIN downline d ON u.sponsor_id = d.id WHERE d.level < %s
                )
                SELECT COUNT(*) as count FROM downline
            """, (user_id, max_depth))
            total_downline = cur.fetchone()["count"] or 0

            cur.execute("""
                SELECT COUNT(*) as count FROM users WHERE sponsor_id = %s
            """, (user_id,))
            direct_referrals = cur.fetchone()["count"] or 0

            cur.execute("""
                WITH RECURSIVE upline AS (
                    SELECT id, sponsor_id, full_name, 1 AS level
                    FROM users WHERE id = %s
                    UNION ALL
                    SELECT u.id, u.sponsor_id, u.full_name, up.level + 1
                    FROM users u
                    INNER JOIN upline up ON u.id = up.sponsor_id
                )
                SELECT id, full_name, level FROM upline WHERE level > 1 ORDER BY level ASC
            """, (user_id,))
            upline_chain = [dict(r) for r in cur.fetchall()]

        return {
            "total_downline": total_downline,
            "direct_referrals": direct_referrals,
            "upline_chain": upline_chain
        }
    except Exception as e:
        logger.error(f"Network profile error | user={user_id} | error={str(e)}")
        return {}


def get_user_purchase_history(user_id, limit=100):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT p.name as package_name, p.price, o.status, o.created_at
                FROM orders o
                JOIN subscription_plans p ON o.package_id = p.id
                WHERE o.user_id = %s
                ORDER BY o.created_at DESC
                LIMIT %s
            """, (user_id, limit))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        # FIX: previously silent (bare except, no logging) -- failures
        # here were invisible in logs, unlike every other function in
        # this file.
        logger.error(f"Purchase history error | user={user_id} | error={str(e)}")
        return []


def get_user_audit_trail(user_id, limit=50):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT action, metadata, created_at
                FROM audit_logs
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        # FIX: same silent-failure issue as get_user_purchase_history.
        logger.error(f"Audit trail error | user={user_id} | error={str(e)}")
        return []
