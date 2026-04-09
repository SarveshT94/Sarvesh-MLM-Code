from app.db import get_cursor


# -----------------------------------
# Get Payout Report (Admin)
# -----------------------------------
def get_payout_report():
    """
    Fetch all payout/withdrawal data for admin dashboard
    """
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT 
                    wr.id,
                    wr.user_id,
                    u.full_name,
                    wr.amount,
                    wr.status,
                    wr.created_at
                FROM withdraw_requests wr
                JOIN users u ON wr.user_id = u.id
                ORDER BY wr.created_at DESC
            """)

            data = cur.fetchall()

            return {
                "status": "success",
                "data": data
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
