from app.db import get_db_connection
from psycopg2.extras import RealDictCursor


# -----------------------------------
# Get user by email
# -----------------------------------
def get_user_by_email(email):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT * FROM users WHERE email = %s",
        (email,)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return user


# -----------------------------------
# Get user by phone
# -----------------------------------
def get_user_by_phone(phone):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT * FROM users WHERE phone = %s",
        (phone,)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return user


# -----------------------------------
# Get user by referral code
# -----------------------------------
def get_user_by_referral_code(referral_code):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT * FROM users WHERE referral_code = %s",
        (referral_code,)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return user


# -----------------------------------
# Create new user
# -----------------------------------
def create_user(role_id, full_name, email, phone, password_hash, referral_code, sponsor_id):
    conn = get_db_connection()

    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO users
            (role_id, full_name, email, phone, password_hash, referral_code, sponsor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            role_id,
            full_name,
            email,
            phone,
            password_hash,
            referral_code,
            sponsor_id
        ))

        user_id = cur.fetchone()[0]

        conn.commit()

        cur.close()
        conn.close()

        return user_id

    except Exception as e:
        conn.rollback()
        conn.close()
        raise e
