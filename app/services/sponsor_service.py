from app.db import get_cursor


def get_sponsor_chain(user_id, max_levels=10):
    """
    Get sponsor upline chain
    """

    sponsors = []
    current_user = user_id

    with get_cursor() as cur:

        for _ in range(max_levels):

            cur.execute("""
                SELECT sponsor_id
                FROM users
                WHERE id = %s
            """, (current_user,))

            result = cur.fetchone()

            if not result:
                break

            sponsor_id = result["sponsor_id"]

            if not sponsor_id:
                break

            sponsors.append(sponsor_id)

            current_user = sponsor_id

    return sponsors
