"""
app/services/admin/tree_service.py — REWRITE

Why this changed
----------------
The old build_tree() issued ONE database query per node, recursively. A user
with 5,000 downline = 5,000 queries on a single page load. Worse, it was
wrapped in @cache.memoize(timeout=1) — a one-second cache that is useless and
(under SimpleCache) per-process. This version:

  * fetches the entire depth-bounded subtree in ONE query using ltree
    (migration 004), then assembles parent->children in memory (O(n));
  * caches the assembled tree in Redis for 300 s;
  * exposes invalidate so edits/activations can bust it.
"""
from __future__ import annotations

import logging

from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)
TREE_TTL = 300


def get_user_tree(user_id, max_depth: int = 10):
    cached = cache.get(f"tree:full:{user_id}:{max_depth}")
    if cached is not None:
        return cached

    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id AS user_id, u.full_name, u.email, u.phone,
                       u.referral_code, u.is_active, u.created_at,
                       u.sponsor_id, u.direct_count, u.total_team_count,
                       (nlevel(u.tree_path) - nlevel(root.tree_path)) AS level
                FROM users u
                JOIN users root ON root.id = %s
                WHERE u.tree_path <@ root.tree_path
                  AND nlevel(u.tree_path) - nlevel(root.tree_path) <= %s
                ORDER BY level ASC, u.created_at ASC
                """,
                (user_id, max_depth),
            )
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            return None

        nodes: dict = {}
        for r in rows:
            r["children"] = []
            nodes[str(r["user_id"])] = r

        root = nodes[str(user_id)]
        for r in rows:
            pid = str(r["sponsor_id"]) if r.get("sponsor_id") is not None else None
            if pid and pid in nodes and r["user_id"] != root["user_id"]:
                nodes[pid]["children"].append(r)

        cache.set(f"tree:full:{user_id}:{max_depth}", root, timeout=TREE_TTL)
        return root
    except Exception as e:
        logger.error("get_user_tree error user=%s: %s", user_id, e)
        return None


def get_children(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, full_name, email, phone, referral_code, is_active,
                   created_at, direct_count, total_team_count
            FROM users WHERE sponsor_id = %s ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def invalidate_tree(user_id):
    try:
        cache.delete(f"tree:full:{user_id}:10")
    except Exception:
        pass
