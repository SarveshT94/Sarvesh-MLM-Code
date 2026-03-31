from app.db import get_cursor
from datetime import datetime


def admin_wallet_adjust(user_id, amount, remark):

    with get_cursor() as cur:

        cur.execute(
            """
            INSERT INTO wallet_ledger
            (user_id, amount, remark, created_at)
            VALUES (%s,%s,%s,%s)
            """,
            (user_id, amount, remark, datetime.utcnow())
        )
