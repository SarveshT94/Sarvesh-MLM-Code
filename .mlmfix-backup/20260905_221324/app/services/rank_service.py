"""
app/services/rank_service.py  —  REWRITE (drop-in replacement)

Fixes
-----
* evaluate_user_rank_and_bonus() used to call get_total_team_count(), which
  opened a SECOND connection in the middle of the payout transaction. With a
  transaction pool that deadlocks / self-blocks. All reads now use the open
  cursor.
* Team size / volume used unbounded recursive CTEs run for EVERY earner on
  EVERY purchase. Now: team size reads the denormalised counter and volume is
  one indexed subtree aggregate over ltree.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.db import get_cursor
from app.services.team_service import get_total_team_count

logger = logging.getLogger(__name__)
TWO = Decimal("0.01")


def _volume(c, user_id) -> Decimal:
    """Total package volume in the whole subtree (ltree, indexed)."""
    c.execute(
        """
        SELECT COALESCE(SUM(o.amount), 0) AS v
        FROM orders o
        JOIN users d   ON d.id = o.user_id
        JOIN users root ON root.id = %s
        WHERE d.tree_path <@ root.tree_path
        """,
        (user_id,),
    )
    return Decimal(str(c.fetchone()["v"]))


def _rank_level(c, user_id):
    c.execute("SELECT COALESCE(rank_level, 1) AS rl FROM users WHERE id = %s", (user_id,))
    row = c.fetchone()
    return int(row["rl"]) if row else 1


def get_user_rank_data(user_id):
    with get_cursor() as cur:
        current_volume = _volume(cur, user_id)
        team_size = get_total_team_count(user_id)
        current_rank_level = _rank_level(cur, user_id)

        cur.execute("SELECT rank_name FROM rank_rules WHERE level = %s", (current_rank_level,))
        row = cur.fetchone()
        current_rank_name = row["rank_name"] if row else "Associate"

        cur.execute(
            """
            SELECT rank_name, req_business_vol, req_team_size
            FROM rank_rules WHERE level > %s ORDER BY level ASC LIMIT 1
            """,
            (current_rank_level,),
        )
        nxt = cur.fetchone()
        if nxt:
            next_rank_name = nxt["rank_name"]
            next_volume = Decimal(str(nxt["req_business_vol"]))
            next_team = nxt["req_team_size"]
            progress = (current_volume / next_volume * 100) if next_volume > 0 else Decimal("0")
        else:
            next_rank_name = "Max Rank Reached"
            next_volume = current_volume
            next_team = team_size
            progress = Decimal("100")

        return {
            "current_rank": current_rank_name,
            "next_rank": next_rank_name,
            "current_volume": float(current_volume),
            "next_rank_volume": float(next_volume),
            "current_team_size": team_size,
            "next_rank_team_size": next_team,
            "progress_percentage": float(min(progress, Decimal("100"))),
        }


def evaluate_user_rank_and_bonus(user_id, cur=None):
    """Promote the user if eligible and pay one-time rank bonuses."""
    from app.services.commission_engine import process_rank_volume_bonus

    def _run(c):
        current_volume = _volume(c, user_id)

        c.execute("SELECT COALESCE(total_team_count, 0) AS ts FROM users WHERE id = %s", (user_id,))
        team_size = int(c.fetchone()["ts"])

        current_rank_level = _rank_level(c, user_id)
        c.execute("SELECT * FROM rank_rules ORDER BY level ASC")
        rules = c.fetchall()

        highest = current_rank_level
        for rule in rules:
            level = int(rule["level"])
            req_vol = Decimal(str(rule["req_business_vol"]))
            req_size = int(rule["req_team_size"])
            bonus_pct = Decimal(str(rule["bonus_percentage"]))

            if current_volume >= req_vol:
                c.execute(
                    "SELECT 1 FROM user_bonus_history WHERE user_id = %s AND rank_level = %s",
                    (user_id, level),
                )
                if not c.fetchone():
                    bonus = (req_vol * bonus_pct / Decimal("100")).quantize(TWO)
                    c.execute(
                        """
                        INSERT INTO user_bonus_history (user_id, rank_level, bonus_amount)
                        VALUES (%s, %s, %s)
                        """,
                        (user_id, level, bonus),
                    )
                    process_rank_volume_bonus(user_id, rule["rank_name"], level, bonus, c)

            if current_volume >= req_vol and team_size >= req_size:
                highest = max(highest, level)

        if highest > current_rank_level:
            c.execute("UPDATE users SET rank_level = %s WHERE id = %s", (highest, user_id))
            logger.info("User %s promoted to rank level %s", user_id, highest)

        return {"status": "success", "current_volume": float(current_volume),
                "team_size": team_size, "rank_level": highest}

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("rank evaluation failed user=%s: %s", user_id, e)
        return {"status": "error", "message": "Evaluation failed"}


def get_user_rank(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT r.rank_name
            FROM users u JOIN rank_rules r ON u.rank_level = r.level
            WHERE u.id = %s
            """,
            (user_id,),
        )
        return cur.fetchone()
