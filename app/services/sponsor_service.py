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
                SELECT sponsor_id 
                FROM upline 
                ORDER BY level ASC;
            """, (user_id, max_levels))

            results = cur.fetchall()

            sponsor_chain = [row['sponsor_id'] for row in results]

            return sponsor_chain

    except Exception as e:
        logger.error(f"Sponsor chain error | user={user_id} | error={str(e)}")
        return []
