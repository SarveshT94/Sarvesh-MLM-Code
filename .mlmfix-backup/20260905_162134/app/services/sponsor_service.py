"""
app/services/sponsor_service.py  —  REWRITE (drop-in replacement)

Accepts an optional open cursor so the upline walk runs INSIDE the caller's
transaction (commission distribution). The recursive CTE is bounded and uses
the indexed sponsor_id link (depth is tiny — payouts only go ~10 levels).
"""
from __future__ import annotations

import logging

from app.db import get_cursor

logger = logging.getLogger(__name__)


def get_sponsor_chain(user_id, max_levels: int = 10, cur=None):
    """
    Return the upline as [{user_id, full_name, email, phone, is_active, level}]
    ordered from the direct sponsor (level 1) upward.
    """
    if not user_id:
        return []

    sql = """
        WITH RECURSIVE upline AS (
            SELECT sponsor_id, 1 AS level
            FROM users
            WHERE id = %s AND sponsor_id IS NOT NULL
            UNION ALL
            SELECT u.sponsor_id, ul.level + 1
            FROM users u
            JOIN upline ul ON u.id = ul.sponsor_id
            WHERE u.sponsor_id IS NOT NULL AND ul.level < %s
        )
        SELECT u.id AS user_id, u.full_name, u.email, u.phone,
               u.is_active, ul.level
        FROM upline ul
        JOIN users u ON u.id = ul.sponsor_id
        ORDER BY ul.level ASC
    """

    def _run(c):
        c.execute(sql, (user_id, max_levels))
        return [dict(r) for r in c.fetchall()]

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("get_sponsor_chain error user=%s: %s", user_id, e)
        return []
