"""
app/services/admin_user_service.py — REWRITE

* get_users_paginated() now orders by id (indexed) and uses the pg_trgm
  indexes from migration 0004 for search (the old ILIKE '%..%' forced a
  sequential scan over 100k rows on every keystroke).
* Adds filters (status) and returns rank/package for a richer table.
* Activate/deactivate invalidate team counters cache.
"""
from __future__ import annotations

import logging
from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)

_USER_COLS = """
    id, full_name, email, phone, referral_code, sponsor_id,
    is_active, rank_level, package_id, created_at
"""


def get_all_users(limit=100):
    with get_cursor() as cur:
        cur.execute(f"SELECT {_USER_COLS} FROM users ORDER BY id DESC LIMIT %s", (limit,))
        return cur.fetchall()


def activate_user(user_id):
    with get_cursor() as cur:
        cur.execute("UPDATE users SET is_active = TRUE, activated_at = COALESCE(activated_at, NOW()) WHERE id = %s",
                    (user_id,))
    cache.delete(f"team:count:{user_id}")
    return True


def deactivate_user(user_id):
    with get_cursor() as cur:
        cur.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
    cache.delete(f"team:count:{user_id}")
    return True


def search_users(keyword, limit=50):
    like = f"%{keyword}%"
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT {_USER_COLS} FROM users
            WHERE full_name ILIKE %s OR email ILIKE %s OR phone ILIKE %s
               OR referral_code ILIKE %s OR id::text = %s
            ORDER BY id DESC LIMIT %s
            """,
            (like, like, like, like, keyword.strip(), limit),
        )
        return cur.fetchall()


def get_users_paginated(page=1, search="", status=None):
    limit = 25
    page = max(1, int(page or 1))
    offset = (page - 1) * limit

    where, params = [], []
    if search:
        like = f"%{search.strip()}%"
        where.append("(full_name ILIKE %s OR email ILIKE %s OR phone ILIKE %s "
                     "OR referral_code ILIKE %s OR id::text = %s)")
        params += [like, like, like, like, search.strip()]
    if status in ("active", "inactive"):
        where.append("is_active = %s")
        params.append(status == "active")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with get_cursor() as cur:
        cur.execute(
            f"SELECT {_USER_COLS} FROM users {where_sql} ORDER BY id DESC LIMIT %s OFFSET %s",
            (*params, limit, offset),
        )
        users = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) AS c FROM users {where_sql}", params)
        total = int(cur.fetchone()["c"])

    pages = (total + limit - 1) // limit
    return {"users": users, "total": total, "page": page, "pages": pages}


def get_user_by_id(user_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()
