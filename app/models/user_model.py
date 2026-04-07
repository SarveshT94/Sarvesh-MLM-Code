from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)

# -----------------------------------
# Get user by email
# -----------------------------------
def get_user_by_email(email):
    """Fetch a user by their email address."""
    try:
        email = email.lower().strip()

        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,)
            )
            return cur.fetchone()

    except Exception as e:
        logger.error(f"Error fetching user by email: {str(e)}")
        return None


# -----------------------------------
# Get user by phone
# -----------------------------------
def get_user_by_phone(phone):
    """Fetch a user by their phone number."""
    try:
        phone = phone.strip()

        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE phone = %s",
                (phone,)
            )
            return cur.fetchone()

    except Exception as e:
        logger.error(f"Error fetching user by phone: {str(e)}")
        return None


# -----------------------------------
# Get user by referral code
# -----------------------------------
def get_user_by_referral_code(referral_code):
    """Fetch a user by their unique referral code."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE referral_code = %s",
                (referral_code,)
            )
            return cur.fetchone()

    except Exception as e:
        logger.error(f"Error fetching user by referral code: {str(e)}")
        return None


# -----------------------------------
# Create new user (Enterprise Safe)
# -----------------------------------
def create_user(role_id, full_name, email, phone, password_hash, referral_code, sponsor_id):
    """
    Creates a new user and safely commits the transaction.
    """
    try:
        email = email.lower().strip()
        phone = phone.strip()

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

            new_user_id = cur.fetchone()[0]

        logger.info(f"User created successfully: {email}")

        return new_user_id

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return None
