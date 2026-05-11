from app.db import get_cursor
from app.services.commission_engine import distribute_commission
import logging

logger = logging.getLogger(__name__)

"""
BUG FIXED #19: was querying 'package_purchases' table — correct table is 'user_packages'.

BUG FIXED #20: was calling cursor.execute("BEGIN") and cursor.execute("COMMIT")
INSIDE a `with get_cursor() as cur:` block. get_cursor() already manages
transactions (commit on success, rollback on error). Adding manual BEGIN
causes a PostgreSQL warning "there is already a transaction in progress"
and the manual COMMIT can commit a partial state if distribute_commission
fails mid-way. All manual transaction calls removed.
"""


def recalc_user_commissions(user_id, admin_id):
    with get_cursor() as cur:
        # FIXED: was querying 'package_purchases' → correct table is 'user_packages'
        cur.execute("""
            SELECT id, user_id, package_id
            FROM user_packages
            WHERE user_id = %s
        """, (user_id,))
        purchases = cur.fetchall()

        total_recalculated = 0
        for purchase in purchases:
            try:
                distribute_commission(purchase["user_id"], purchase["package_id"])
                total_recalculated += 1
            except Exception as e:
                logger.error(f"Recalc failed for purchase {purchase['id']}: {str(e)}")

        cur.execute("""
            INSERT INTO commission_recalc_logs (admin_id, target_user_id, recalc_type)
            VALUES (%s, %s, %s)
        """, (admin_id, user_id, "user_recalc"))

    return {"total_events": total_recalculated}


def recalc_purchase_commission(purchase_id, admin_id):
    with get_cursor() as cur:
        # FIXED: was querying 'package_purchases'
        cur.execute("""
            SELECT id, user_id, package_id
            FROM user_packages
            WHERE id = %s
        """, (purchase_id,))
        purchase = cur.fetchone()

        if not purchase:
            raise Exception("Purchase not found")

        distribute_commission(purchase["user_id"], purchase["package_id"])

        cur.execute("""
            INSERT INTO commission_recalc_logs (admin_id, reference_id, recalc_type)
            VALUES (%s, %s, %s)
        """, (admin_id, purchase_id, "purchase_recalc"))

    return True


def recalc_date_commissions(date, admin_id):
    with get_cursor() as cur:
        # FIXED: was querying 'package_purchases'
        cur.execute("""
            SELECT id, user_id, package_id
            FROM user_packages
            WHERE DATE(created_at) = %s
        """, (date,))
        purchases = cur.fetchall()

        total = 0
        for purchase in purchases:
            try:
                distribute_commission(purchase["user_id"], purchase["package_id"])
                total += 1
            except Exception as e:
                logger.error(f"Recalc error for purchase {purchase['id']}: {str(e)}")

        cur.execute("""
            INSERT INTO commission_recalc_logs (admin_id, recalc_type, remark)
            VALUES (%s, %s, %s)
        """, (admin_id, "date_recalc", f"Recalculated commissions for {date}"))

    return {"total_events": total}


def recalc_full_system(admin_id):
    with get_cursor() as cur:
        # FIXED: was querying 'package_purchases'
        cur.execute("SELECT id, user_id, package_id FROM user_packages")
        purchases = cur.fetchall()

        total = 0
        errors = 0
        for purchase in purchases:
            try:
                distribute_commission(purchase["user_id"], purchase["package_id"])
                total += 1
            except Exception as e:
                logger.error(f"Full recalc error for purchase {purchase['id']}: {str(e)}")
                errors += 1

        cur.execute("""
            INSERT INTO commission_recalc_logs (admin_id, recalc_type)
            VALUES (%s, %s)
        """, (admin_id, "system_recalc"))

    logger.info(f"Full recalc done | processed={total} | errors={errors}")
    return {"total_events": total, "errors": errors}
