from app.db import get_cursor
from app.utils.referral import generate_unique_referral_code
from app.services.referral_service import get_sponsor_id
from app.utils.security import hash_password
from app.services.commission_service import distribute_commission
from app.services.rank_service import check_and_update_rank

# ------------------------------------------------
# USER REGISTRATION
# ------------------------------------------------
def register_user(full_name, email, phone, password, referral_code):

    try:
        with get_cursor() as cur:

            # ---------------------------
            # CHECK DUPLICATE USER
            # ---------------------------
            cur.execute(
                "SELECT id FROM users WHERE phone=%s OR email=%s",
                (phone, email)
            )
            existing = cur.fetchone()

            if existing:
                return {
                    "success": False,
                    "message": "User already exists"
                }

            # ---------------------------
            # VALIDATE REFERRAL CODE
            # ---------------------------
            sponsor_id = None

            if referral_code:
                sponsor_id = get_sponsor_id(referral_code)

                if sponsor_id is None:
                    return {
                        "success": False,
                        "message": "Invalid referral code"
                    }
            # ---------------------------
            # GENERATE NEW REFERRAL
            # ---------------------------
            new_referral = generate_unique_referral_code()

            # ---------------------------
            # HASH PASSWORD
            # ---------------------------
            password_hash = hash_password(password)

            # ---------------------------
            # CREATE USER
            # ---------------------------
            cur.execute(
                """
                INSERT INTO users
                (role_id, full_name, email, phone, password_hash,
                 referral_code, sponsor_id, is_active, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                RETURNING id
                """,
                (
                    2,
                    full_name,
                    email,
                    phone,
                    password_hash,
                    new_referral,
                    sponsor_id,
                    False
                )
            )

            user = cur.fetchone()
            new_user_id = user["id"]

            # ---------------------------
            # COMMIT (CRITICAL FIX)
            # ---------------------------
            cur.connection.commit()

            # ---------------------------
            # MLM LOGIC
            # ---------------------------
            check_and_update_rank(sponsor_id)

            distribute_commission(
                cur.connection,
                cur,
                new_user_id,
                100
            )

            return {
                "success": True,
                "user_id": new_user_id,
                "referral_code": new_referral
            }

    except Exception as e:
        print("REGISTER ERROR:", str(e))
        return {
            "success": False,
            "message": "Registration failed"
        }


# ------------------------------------------------
# GET USER BY ID
# ------------------------------------------------
def get_user_by_id(user_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        return cur.fetchone()


def get_user_by_email(email):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        return cur.fetchone()


def get_user_profile(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, full_name, email, phone, is_active
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
        return cur.fetchone()


# ------------------------------------------------
# ADMIN USERS TABLE (Pagination)
# ------------------------------------------------
def get_users_paginated(page=1, search=""):

    limit = 20
    offset = (page - 1) * limit
    search_query = f"%{search}%"

    with get_cursor() as cur:
        cur.execute("""
            SELECT id, full_name, email, sponsor_id, created_at
            FROM users
            WHERE full_name ILIKE %s OR email ILIKE %s
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """, (search_query, search_query, limit, offset))

        return cur.fetchall()
