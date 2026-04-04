from app.db import get_cursor
from app.services.commission_engine import distribute_commission

# --------------------------------------------------
# Recalculate commissions for a specific user
# --------------------------------------------------
def recalc_user_commissions(user_id, admin_id):
    with get_cursor() as cursor:
        try:
            cursor.execute("BEGIN")
            cursor.execute("""
                SELECT id, user_id, package_id
                FROM package_purchases
                WHERE user_id = %s
            """, (user_id,))
            purchases = cursor.fetchall()
            
            total_recalculated = 0
            for purchase in purchases:
                # Pointing to the new Enterprise Engine
                distribute_commission(purchase["user_id"], purchase["package_id"])
                total_recalculated += 1

            # log admin action
            cursor.execute("""
                INSERT INTO commission_recalc_logs (admin_id, target_user_id, recalc_type)
                VALUES (%s, %s, %s)
            """, (admin_id, user_id, "user_recalc"))
            
            cursor.execute("COMMIT")
            return {"total_events": total_recalculated}
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

# --------------------------------------------------
# Recalculate commission for a specific purchase
# --------------------------------------------------
def recalc_purchase_commission(purchase_id, admin_id):
    with get_cursor() as cursor:
        try:
            cursor.execute("BEGIN")
            cursor.execute("""
                SELECT id, user_id, package_id
                FROM package_purchases
                WHERE id = %s
            """, (purchase_id,))
            purchase = cursor.fetchone()
            
            if not purchase:
                raise Exception("Purchase not found")

            # Pointing to the new Enterprise Engine
            distribute_commission(purchase["user_id"], purchase["package_id"])

            cursor.execute("""
                INSERT INTO commission_recalc_logs (admin_id, reference_id, recalc_type)
                VALUES (%s, %s, %s)
            """, (admin_id, purchase_id, "purchase_recalc"))
            
            cursor.execute("COMMIT")
            return True
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

# --------------------------------------------------
# Recalculate commissions for a specific date
# --------------------------------------------------
def recalc_date_commissions(date, admin_id):
    with get_cursor() as cursor:
        try:
            cursor.execute("BEGIN")
            cursor.execute("""
                SELECT id, user_id, package_id
                FROM package_purchases
                WHERE DATE(created_at) = %s
            """, (date,))
            purchases = cursor.fetchall()
            
            total = 0
            for purchase in purchases:
                distribute_commission(purchase["user_id"], purchase["package_id"])
                total += 1

            cursor.execute("""
                INSERT INTO commission_recalc_logs (admin_id, recalc_type, remark)
                VALUES (%s, %s, %s)
            """, (admin_id, "date_recalc", f"Recalculated commissions for {date}"))
            
            cursor.execute("COMMIT")
            return {"total_events": total}
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

# --------------------------------------------------
# Recalculate commissions for entire system
# --------------------------------------------------
def recalc_full_system(admin_id):
    with get_cursor() as cursor:
        try:
            cursor.execute("BEGIN")
            cursor.execute("""
                SELECT id, user_id, package_id
                FROM package_purchases
            """)
            purchases = cursor.fetchall()
            
            total = 0
            for purchase in purchases:
                distribute_commission(purchase["user_id"], purchase["package_id"])
                total += 1

            cursor.execute("""
                INSERT INTO commission_recalc_logs (admin_id, recalc_type)
                VALUES (%s, %s)
            """, (admin_id, "system_recalc"))
            
            cursor.execute("COMMIT")
            return {"total_events": total}
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e
