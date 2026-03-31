from app.db import get_db_connection


def check_and_update_rank(user_id):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        # total team size
        cur.execute("""
            WITH RECURSIVE downline AS (

                SELECT id, sponsor_id
                FROM users
                WHERE sponsor_id=%s

                UNION ALL

                SELECT u.id, u.sponsor_id
                FROM users u
                INNER JOIN downline d
                ON u.sponsor_id=d.id
            )

            SELECT COUNT(*) as team_size
            FROM downline
        """, (user_id,))

        team_size = cur.fetchone()["team_size"]

        # find rank
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

        # current rank
        cur.execute("""
            SELECT rank_id
            FROM users
            WHERE id=%s
        """, (user_id,))

        current_rank = cur.fetchone()["rank_id"]

        if rank["id"] != current_rank:

            cur.execute("""
                UPDATE users
                SET rank_id=%s
                WHERE id=%s
            """, (rank["id"], user_id))

            conn.commit()

    finally:

        cur.close()
        conn.close()


def get_user_rank(user_id):

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT r.rank_name
            FROM users u
            JOIN ranks r
            ON u.rank_id=r.id
            WHERE u.id=%s
        """, (user_id,))

        return cur.fetchone()

    finally:

        cur.close()
        conn.close()
