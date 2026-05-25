from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def get_sponsor_chain(user_id, max_levels=10):
    """
    Enterprise Genealogy Engine (Hardened):
    - Recursive CTE (fast)
    - Error safe
    - Logging enabled
    """

    if not user_id:
        return []

    try:
        with get_cursor() as cur:
            # We join the users table here to get the actual names/emails for the UI
            cur.execute("""
                WITH RECURSIVE upline AS (
                    SELECT sponsor_id, 1 AS level
                    FROM users
                    WHERE id = %s AND sponsor_id IS NOT NULL

                    UNION ALL

                    SELECT u.sponsor_id, ul.level + 1
                    FROM users u
                    INNER JOIN upline ul ON u.id = ul.sponsor_id
                    WHERE u.sponsor_id IS NOT NULL AND ul.level < %s
                )
                SELECT u.id as user_id, u.full_name, u.email, u.phone, u.is_active, ul.level
                FROM upline ul
                JOIN users u ON ul.sponsor_id = u.id
                ORDER BY ul.level ASC;
            """, (user_id, max_levels))

            # Fetch all details as dictionaries, not just a list of IDs
            return cur.fetchall()

    except Exception as e:
        logger.error(f"Sponsor chain error | user={user_id} | error={str(e)}")
        return []
