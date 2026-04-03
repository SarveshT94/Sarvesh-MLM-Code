from app.db import get_cursor

def get_sponsor_chain(user_id, max_levels=10):
    """
    Enterprise Genealogy Engine:
    Uses a Recursive CTE to fetch the entire upline in a single, lightning-fast query.
    """
    with get_cursor() as cur:
        # The RECURSIVE query pushes the heavy lifting to the PostgreSQL C-engine
        cur.execute("""
            WITH RECURSIVE upline AS (
                -- 1. Base Case: Find the direct sponsor of the buyer
                SELECT sponsor_id, 1 AS level
                FROM users
                WHERE id = %s AND sponsor_id IS NOT NULL
                
                UNION ALL
                
                -- 2. Recursive Step: Find the sponsor's sponsor, looping until max_levels
                SELECT u.sponsor_id, ul.level + 1
                FROM users u
                INNER JOIN upline ul ON u.id = ul.sponsor_id
                WHERE u.sponsor_id IS NOT NULL AND ul.level < %s
            )
            -- 3. Return the clean list ordered from Level 1 to Level X
            SELECT sponsor_id 
            FROM upline 
            ORDER BY level ASC;
        """, (user_id, max_levels))
        
        results = cur.fetchall()
        
        # Extract just the IDs into a simple Python list: [15, 8, 2]
        # Level 1 is index 0, Level 2 is index 1, etc.
        sponsor_chain = [row['sponsor_id'] for row in results]
        
        return sponsor_chain
