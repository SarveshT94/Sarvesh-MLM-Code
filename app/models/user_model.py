from app.db import get_cursor

# -----------------------------------
# Get user by email
# -----------------------------------
def get_user_by_email(email):
    """Fetch a user by their email address."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )
        return cur.fetchone()


# -----------------------------------
# Get user by phone
# -----------------------------------
def get_user_by_phone(phone):
    """Fetch a user by their phone number."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM users WHERE phone = %s",
            (phone,)
        )
        return cur.fetchone()


# -----------------------------------
# Get user by referral code
# -----------------------------------
def get_user_by_referral_code(referral_code):
    """Fetch a user by their unique referral code."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM users WHERE referral_code = %s",
            (referral_code,)
        )
        return cur.fetchone()


# -----------------------------------
# Create new user (Enterprise Safe)
# -----------------------------------
def create_user(role_id, full_name, email, phone, password_hash, referral_code, sponsor_id):
    """
    Creates a new user and safely commits the transaction.
    If anything fails, the database automatically rolls back.
    """
    with get_cursor() as cur:
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
        
        # Because we use RealDictCursor, we fetch the ID by its column name
        result = cur.fetchone()
        user_id = result['id']
        
        return user_id
