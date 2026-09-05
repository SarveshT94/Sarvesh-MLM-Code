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
          AND o.status = 'completed'
        """,
        (user_id,),
    )
    return Decimal(str(c.fetchone()["v"]))


def _rank_level(c, user_id):
    """0 = no rank achieved yet (shown as 'Distributor')."""
    c.execute("SELECT COALESCE(rank_level, 0) AS rl FROM users WHERE id = %s", (user_id,))
    row = c.fetchone()
    return int(row["rl"]) if row else 0


def get_user_rank_data(user_id):
    """
    Rank snapshot with explicit 'achieved vs remaining' figures so the UI can
    show: current rank, next rank, business done / required / remaining,
    team done / required / remaining, and the fast-action bonus on offer.
    A rank is awarded only when BOTH the volume AND team-size targets are met.
    """
    with get_cursor() as cur:
        current_volume = _volume(cur, user_id)
        team_size = get_total_team_count(user_id)
        current_rank_level = _rank_level(cur, user_id)

        cur.execute("""
            SELECT level, rank_name, req_team_size, req_business_vol, bonus_percentage
            FROM rank_rules ORDER BY level ASC
        """)
        all_rules = [dict(r) for r in cur.fetchall()]

        cur_rule = next((r for r in all_rules if r["level"] == current_rank_level), None)
        current_rank_name = cur_rule["rank_name"] if cur_rule else "Distributor"

        # Next rank = lowest level above current that the user has NOT fully
        # qualified for (needs BOTH volume and team size).
        nxt = None
        for r in all_rules:
            if r["level"] <= current_rank_level:
                continue
            req_vol = Decimal(str(r["req_business_vol"]))
            req_team = int(r["req_team_size"])
            if current_volume < req_vol or team_size < req_team:
                nxt = r
                break

        if nxt:
            next_rank_name = nxt["rank_name"]
            req_vol = Decimal(str(nxt["req_business_vol"]))
            req_team = int(nxt["req_team_size"])
            bonus_pct = Decimal(str(nxt["bonus_percentage"]))

            vol_done = min(current_volume, req_vol)
            vol_remaining = max(req_vol - current_volume, Decimal("0"))
            team_done = min(team_size, req_team)
            team_remaining = max(req_team - team_size, 0)

            vol_progress = (vol_done / req_vol * 100) if req_vol > 0 else Decimal("100")
            team_progress = Decimal(team_done) / Decimal(req_team) * 100 if req_team else Decimal("100")
            # Overall progress = the weaker of the two requirements.
            overall = min(vol_progress, team_progress)
            qualified = current_volume >= req_vol and team_size >= req_team

            return {
                "current_rank": current_rank_name,
                "current_rank_level": current_rank_level,
                "next_rank": next_rank_name,
                "rank_achieved": False,
                "fast_action_bonus_pct": float(bonus_pct),
                # business volume
                "current_volume": float(current_volume),
                "next_rank_volume": float(req_vol),
                "volume_done": float(vol_done),
                "volume_remaining": float(vol_remaining.quantize(Decimal("0.01"))),
                "volume_progress_pct": float(vol_progress.quantize(Decimal("0.01"))),
                # team
                "current_team_size": team_size,
                "next_rank_team_size": req_team,
                "team_done": int(team_done),
                "team_remaining": int(team_remaining),
                "team_progress_pct": float(team_progress.quantize(Decimal("0.01"))),
                # overall
                "qualified_for_next": qualified,
                "progress_percentage": float(min(overall, Decimal("100")).quantize(Decimal("0.01"))),
            }

        # Highest rank reached.
        top = all_rules[-1] if all_rules else {}
        return {
            "current_rank": current_rank_name,
            "current_rank_level": current_rank_level,
            "next_rank": "Max Rank Reached",
            "rank_achieved": True,
            "fast_action_bonus_pct": 0.0,
            "current_volume": float(current_volume),
            "next_rank_volume": float(current_volume),
            "volume_done": float(current_volume),
            "volume_remaining": 0.0,
            "volume_progress_pct": 100.0,
            "current_team_size": team_size,
            "next_rank_team_size": team_size,
            "team_done": team_size,
            "team_remaining": 0,
            "team_progress_pct": 100.0,
            "qualified_for_next": True,
            "progress_percentage": 100.0,
            "top_rank": top.get("rank_name"),
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

            # A rank (and its one-time bonus) is earned ONLY when BOTH the
            # team-size AND the business-volume targets are met.
            if current_volume >= req_vol and team_size >= req_size:
                highest = max(highest, level)
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
