# app/services/rank_service.py

from app.db import get_cursor


# -----------------------------------
# CHECK & UPDATE USER RANK
# -----------------------------------
def check_and_update_rank(user_id, cur=None):
    """
    Updates user rank based on team size.
    Supports:
    - standalone usage
    - transactional usage (with cur)
    """

    def _process(cur):

        # ---------------------------
        # Calculate total team size
        # ---------------------------
        cur.execute("""
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

            SELECT COUNT(*) AS team_size
            FROM downline
        """, (user_id,))

        team_size = cur.fetchone()["team_size"]

        # ---------------------------
        # Find applicable rank
        # ---------------------------
        cur.execute("""
            SELECT id, rank_name
            FROM ranks
            WHERE team_required <= %s
            ORDER BY team_required DESC
            LIMIT 1
        """, (team_size,))

        rank = cur.fetchone()

        if not rank:
            return

        # ---------------------------
        # Get current rank
        # ---------------------------
        cur.execute("""
            SELECT rank_id
            FROM users
            WHERE id = %s
        """, (user_id,))

        current_rank = cur.fetchone()["rank_id"]

        # ---------------------------
        # Update rank if changed
        # ---------------------------
        if rank["id"] != current_rank:

            cur.execute("""
                UPDATE users
                SET rank_id = %s
                WHERE id = %s
            """, (rank["id"], user_id))

    # ---------------------------
    # Execution Mode
    # ---------------------------
    if cur:
        _process(cur)
    else:
        with get_cursor() as new_cur:
            _process(new_cur)


# -----------------------------------
# GET USER RANK
# -----------------------------------
def get_user_rank(user_id):
    """
    Fetch user rank name
    """
    with get_cursor() as cur:

        cur.execute("""
            SELECT r.rank_name
            FROM users u
            JOIN ranks r ON u.rank_id = r.id
            WHERE u.id = %s
        """, (user_id,))

        return cur.fetchone()
