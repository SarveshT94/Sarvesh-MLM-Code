"""
app/services/team_service.py  —  REWRITE (drop-in replacement)

Why this changed
----------------
The old version answered "how big is my team?" and "give me the tree" with
recursive CTEs that walk the ENTIRE downline on every page load, and the
admin tree service did it with one SQL query PER node (N+1). At 1 lakh users
a single dashboard click could fire thousands of queries.

This version uses the materialised ltree genealogy path (`users.tree_path`)
and denormalised counters added in migration 0004:

  * direct_count        -> number of direct referrals (kept by trigger)
  * total_team_count    -> size of whole subtree (kept by trigger)
  * tree_path           -> e.g. 1.5.12  => subtree = descendants via `<@`

All public function names/signatures are preserved so the rest of the app
keeps working, but they are now O(subtree) index scans instead of full
recursive walks. Results are cached in Redis and invalidated when the
network changes.
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEPTH = 20
_TEAM_TTL = 120          # seconds for short-lived team aggregates
_TREE_TTL = 300          # seconds for tree payloads


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt(row: dict) -> dict:
    """Serialise a user row into JSON-safe data for the API / templates."""
    if not row:
        return row
    out = dict(row)
    out["id"] = str(out.get("id"))
    if out.get("sponsor_id") is not None:
        out["sponsor_id"] = str(out["sponsor_id"])
    out["is_active"] = bool(out.get("is_active", False))
    out["rank"] = out.get("rank") or "Distributor"
    if isinstance(out.get("created_at"), datetime):
        out["created_at"] = out["created_at"].isoformat()
    return out


# ---------------------------------------------------------------------------
# 1. Direct (Level-1) team
# ---------------------------------------------------------------------------
def get_level_1_team(user_id):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.email,
                       u.phone, u.is_active,
                       COALESCE(rr.rank_name, 'Distributor') AS rank,
                       u.rank_level, u.package_id,
                       u.direct_count, u.total_team_count, u.created_at
                FROM users u
                LEFT JOIN rank_rules rr ON rr.level = u.rank_level
                WHERE u.sponsor_id = %s
                ORDER BY u.created_at DESC
                """,
                (user_id,),
            )
            return [_fmt(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_level_1_team error user=%s: %s", user_id, e)
        return []


# ---------------------------------------------------------------------------
# 2. Total team count  (denormalised -> O(1) read)
# ---------------------------------------------------------------------------
def get_total_team_count(user_id, max_depth: int = DEFAULT_MAX_DEPTH) -> int:
    if not user_id:
        return 0

    cached = cache.get(f"team:count:{user_id}")
    if cached is not None:
        return int(cached)

    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(total_team_count, 0) AS count FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            count = int(row["count"]) if row else 0
        cache.set(f"team:count:{user_id}", count, timeout=_TEAM_TTL)
        return count
    except Exception as e:
        logger.error("get_total_team_count error user=%s: %s", user_id, e)
        return 0


def get_direct_count(user_id) -> int:
    if not user_id:
        return 0
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(direct_count, 0) AS c FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return int(row["c"]) if row else 0
    except Exception as e:
        logger.error("get_direct_count error user=%s: %s", user_id, e)
        return 0


def get_active_count(user_id) -> int:
    """Active members anywhere in the subtree (ltree subtree, indexed)."""
    if not user_id:
        return 0
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM users u
                JOIN users root ON root.id = %s
                WHERE u.tree_path IS NOT NULL
                  AND root.tree_path IS NOT NULL
                  AND u.tree_path <@ root.tree_path
                  AND u.id <> root.id
                  AND u.is_active = TRUE
                """,
                (user_id,),
            )
            return int(cur.fetchone()["c"])
    except Exception as e:
        logger.error("get_active_count error user=%s: %s", user_id, e)
        return 0


# ---------------------------------------------------------------------------
# 3. Team by a specific level  (nlevel difference on ltree)
# ---------------------------------------------------------------------------
def get_team_by_level(user_id, level: int):
    if not user_id or not level or level <= 0:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.email,
                       u.phone, u.is_active,
                       COALESCE(rr.rank_name, 'Distributor') AS rank,
                       u.rank_level,
                       u.direct_count, u.total_team_count, u.created_at
                FROM users u
                LEFT JOIN rank_rules rr ON rr.level = u.rank_level
                JOIN users root ON root.id = %s
                WHERE u.tree_path IS NOT NULL
                  AND root.tree_path IS NOT NULL
                  AND u.tree_path <@ root.tree_path
                  AND nlevel(u.tree_path) - nlevel(root.tree_path) = %s
                ORDER BY u.created_at DESC
                """,
                (user_id, level),
            )
            return [_fmt(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_team_by_level error user=%s level=%s: %s", user_id, level, e)
        return []


# ---------------------------------------------------------------------------
# 4. Full genealogy  — depth-bounded, ONE query (no N+1)
# ---------------------------------------------------------------------------
def get_genealogy_tree(user_id, max_depth: int = DEFAULT_MAX_DEPTH):
    """
    Return a FLAT list of the subtree (root included), each row tagged with
    its relative `level` (root = 0). One bounded SQL query.
    """
    if not user_id:
        return []

    cached = cache.get(f"team:tree:{user_id}:{max_depth}")
    if cached is not None:
        return cached

    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.email,
                       u.phone, u.is_active,
                       COALESCE(rr.rank_name, 'Distributor') AS rank,
                       u.rank_level, u.package_id,
                       u.direct_count, u.total_team_count, u.created_at,
                       (nlevel(u.tree_path) - nlevel(root.tree_path)) AS level
                FROM users u
                LEFT JOIN rank_rules rr ON rr.level = u.rank_level
                JOIN users root ON root.id = %s
                WHERE u.tree_path IS NOT NULL
                  AND root.tree_path IS NOT NULL
                  AND u.tree_path <@ root.tree_path
                  AND nlevel(u.tree_path) - nlevel(root.tree_path) <= %s
                ORDER BY level ASC, u.created_at ASC
                """,
                (user_id, max_depth),
            )
            rows = [_fmt(r) for r in cur.fetchall()]

        cache.set(f"team:tree:{user_id}:{max_depth}", rows, timeout=_TREE_TTL)
        return rows
    except Exception as e:
        logger.error("get_genealogy_tree error user=%s: %s", user_id, e)
        return []


# ---------------------------------------------------------------------------
# 5. NEW — drill-down node used by the "My Team" UI
# ---------------------------------------------------------------------------
def get_team_node(user_id, viewer_id=None, page: int = 1, page_size: int = 12,
                  rank: str | None = None, status: str | None = None):
    """
    Build the payload for ONE node of the drill-down team view.

    The UI calls this with the *currently selected* member's id. Clicking a
    child re-calls the same endpoint with that child's id, so "the audit
    drill follows the selected member".

    Returns the node header (YOU / member summary) + ONE page of direct
    children. Children are NOT expanded server-side; each child carries its
    own `has_team` / `total_team_count`, so the browser only fetches the next
    level when the user clicks "Drill". This is what keeps it fast at scale.
    """
    if not user_id:
        return None

    page = max(1, int(page or 1))
    page_size = min(48, max(1, int(page_size or 12)))
    offset = (page - 1) * page_size

    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.email,
                       u.phone, u.is_active,
                       COALESCE(rr.rank_name, 'Distributor') AS rank,
                       u.rank_level, u.package_id,
                       sp.name AS package_name,
                       u.direct_count, u.total_team_count,
                       (SELECT COUNT(*) FROM users d
                          JOIN users r ON r.id = u.id
                         WHERE d.tree_path <@ r.tree_path AND d.id <> u.id
                           AND d.is_active = TRUE) AS active_count,
                       u.created_at
                FROM users u
                LEFT JOIN rank_rules rr ON rr.level = u.rank_level
                LEFT JOIN subscription_plans sp ON sp.id = u.package_id
                WHERE u.id = %s
                """,
                (user_id,),
            )
            node = cur.fetchone()
            if not node:
                return None

            from_sql = ("FROM users c "
                        "LEFT JOIN rank_rules crr ON crr.level = c.rank_level")
            where = ["c.sponsor_id = %s"]
            params: list = [user_id]
            if status == "active":
                where.append("c.is_active = TRUE")
            elif status == "inactive":
                where.append("c.is_active = FALSE")
            if rank:
                where.append("crr.rank_name = %s")
                params.append(rank)

            where_sql = " AND ".join(where)

            cur.execute(
                f"""
                SELECT c.id, c.sponsor_id, c.referral_code, c.full_name, c.email,
                       c.phone, c.is_active,
                       COALESCE(crr.rank_name, 'Distributor') AS rank,
                       c.rank_level, c.package_id,
                       c.direct_count, c.total_team_count, c.created_at
                {from_sql}
                WHERE {where_sql}
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, page_size, offset),
            )
            children = [_fmt(r) for r in cur.fetchall()]

            cur.execute(
                f"SELECT COUNT(*) AS c {from_sql} WHERE {where_sql}",
                params,
            )
            total_children = int(cur.fetchone()["c"])

        node = _fmt(node)
        is_self = viewer_id is not None and str(viewer_id) == str(user_id)

        return {
            "node": {
                "id": node["id"],
                "label": "YOU" if is_self else f"M{node['id']}",
                "full_name": node.get("full_name"),
                "referral_code": node.get("referral_code"),
                "rank": node.get("rank") or "Distributor",
                "package_name": node.get("package_name"),
                "is_active": node.get("is_active"),
                "joined": node.get("created_at"),
            },
            "stats": {
                "total_team": int(node.get("total_team_count") or 0),
                "direct_referrals": int(node.get("direct_count") or 0),
                "active": int(node.get("active_count") or 0),
                "rank": node.get("rank") or "Distributor",
            },
            "level": 1,
            "children": children,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_children,
                "pages": (total_children + page_size - 1) // page_size,
            },
        }
    except Exception as e:
        logger.error("get_team_node error user=%s: %s", user_id, e)
        return None


# ---------------------------------------------------------------------------
# 6. Network profile + history (admin drill)
# ---------------------------------------------------------------------------
def get_user_network_profile(user_id, max_depth: int = DEFAULT_MAX_DEPTH):
    if not user_id:
        return {}
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.direct_count, u.total_team_count,
                       (SELECT COUNT(*) FROM users d
                          JOIN users r ON r.id = u.id
                         WHERE d.tree_path <@ r.tree_path AND d.id <> u.id
                           AND d.is_active = TRUE) AS active_count
                FROM users u WHERE u.id = %s
                """,
                (user_id,),
            )
            stats = cur.fetchone() or {}

            cur.execute(
                """
                WITH RECURSIVE upline AS (
                    SELECT id, sponsor_id, full_name, 1 AS level
                    FROM users WHERE id = %s
                    UNION ALL
                    SELECT p.id, p.sponsor_id, p.full_name, up.level + 1
                    FROM users p JOIN upline up ON p.id = up.sponsor_id
                )
                SELECT id, full_name, level FROM upline
                WHERE level > 1 ORDER BY level ASC
                """,
                (user_id,),
            )
            upline_chain = [dict(r) for r in cur.fetchall()]

        return {
            "total_downline": int(stats.get("total_team_count", 0) or 0),
            "direct_referrals": int(stats.get("direct_count", 0) or 0),
            "active_count": int(stats.get("active_count", 0) or 0),
            "upline_chain": upline_chain,
        }
    except Exception as e:
        logger.error("get_user_network_profile error user=%s: %s", user_id, e)
        return {}


def get_user_purchase_history(user_id, limit: int = 100):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT p.name AS package_name, p.price, o.status, o.created_at
                FROM orders o
                JOIN subscription_plans p ON o.package_id = p.id
                WHERE o.user_id = %s
                ORDER BY o.created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_user_purchase_history error user=%s: %s", user_id, e)
        return []


def get_user_audit_trail(user_id, limit: int = 50):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT action, metadata, created_at
                FROM audit_logs
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_user_audit_trail error user=%s: %s", user_id, e)
        return []


# ---------------------------------------------------------------------------
# 7. Cache invalidation — call whenever a user is added / sponsor changes /
#    a package is purchased. Cheap and safe to call repeatedly.
# ---------------------------------------------------------------------------
def invalidate_team_cache(user_id):
    try:
        cache.delete(f"team:count:{user_id}")
        cache.delete_memoized(get_genealogy_tree)
    except Exception:
        pass
