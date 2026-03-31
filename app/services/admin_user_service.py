from app.db import get_cursor


# ---------------------------------------------------
# GET ALL USERS (LIMITED)
# ---------------------------------------------------

def get_all_users(limit=100):

    with get_cursor() as cur:

        cur.execute("""
            SELECT
                id,
                full_name,
                email,
                phone,
                referral_code,
                sponsor_id,
                is_active,
                created_at
            FROM users
            ORDER BY id DESC
            LIMIT %s
        """, (limit,))

        users = cur.fetchall()

    return users


from app.db import get_cursor


# ------------------------------------------------
# ACTIVATE USER
# ------------------------------------------------
def activate_user(user_id):

    with get_cursor() as cur:

        cur.execute("""
            UPDATE users
            SET is_active = TRUE
            WHERE id = %s
        """, (user_id,))

    return True


# ------------------------------------------------
# DEACTIVATE USER
# ------------------------------------------------
def deactivate_user(user_id):

    with get_cursor() as cur:

        cur.execute(
            "UPDATE users SET is_active = FALSE WHERE id = %s",
            (user_id,)
        )

        print("Rows Updated:", cur.rowcount)

    return True

# ---------------------------------------------------
# SEARCH USERS
# ---------------------------------------------------

def search_users(keyword):

    search_query = f"%{keyword}%"

    with get_cursor() as cur:

        cur.execute("""
            SELECT
                id,
                full_name,
                email,
                phone,
                referral_code,
                sponsor_id,
                is_active,
                created_at
            FROM users
            WHERE
                full_name ILIKE %s
                OR email ILIKE %s
                OR phone ILIKE %s
            ORDER BY id DESC
            LIMIT 50
        """, (
            search_query,
            search_query,
            search_query
        ))

        users = cur.fetchall()

    return users


# ---------------------------------------------------
# PAGINATION + SEARCH (ADMIN USERS TABLE)
# ---------------------------------------------------

def get_users_paginated(page=1, search=""):

    limit = 20
    offset = (page - 1) * limit

    with get_cursor() as cur:

        # -------------------------------
        # NO SEARCH
        # -------------------------------
        if search == "":

            cur.execute("""
                SELECT
                    id,
                    full_name,
                    email,
                    phone,
                    referral_code,
                    sponsor_id,
                    is_active,
                    created_at
                FROM users
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))

            users = cur.fetchall()

            cur.execute("SELECT COUNT(*) FROM users")
            total = cur.fetchone()["count"]

        # -------------------------------
        # SEARCH MODE
        # -------------------------------
        else:

            search_query = f"%{search}%"

            cur.execute("""
                SELECT
                    id,
                    full_name,
                    email,
                    phone,
                    referral_code,
                    sponsor_id,
                    is_active,
                    created_at
                FROM users
                WHERE
                    full_name ILIKE %s
                    OR email ILIKE %s
                    OR phone ILIKE %s
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """, (
                search_query,
                search_query,
                search_query,
                limit,
                offset
            ))

            users = cur.fetchall()

            cur.execute("""
                SELECT COUNT(*)
                FROM users
                WHERE
                    full_name ILIKE %s
                    OR email ILIKE %s
                    OR phone ILIKE %s
            """, (
                search_query,
                search_query,
                search_query
            ))

            total = cur.fetchone()["count"]

    pages = (total + limit - 1) // limit

    return {
        "users": users,
        "total": total,
        "page": page,
        "pages": pages
    }


# ---------------------------------------------------
# GET SINGLE USER
# ---------------------------------------------------

def get_user_by_id(user_id):

    with get_cursor() as cur:

        cur.execute("""
            SELECT *
            FROM users
            WHERE id = %s
        """, (user_id,))

        user = cur.fetchone()

    return user
