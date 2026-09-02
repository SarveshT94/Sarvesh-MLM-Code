from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)

def get_user_by_email(email):
    try:
        email = email.lower().strip()
        with get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user by email: {str(e)}")
        return None

def get_user_by_phone(phone):
    try:
        phone = phone.strip()
        with get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user by phone: {str(e)}")
        return None

def get_user_by_referral_code(referral_code):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE referral_code = %s", (referral_code,))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user by referral code: {str(e)}")
        return None

def create_user(role_id, full_name, email, phone, password_hash, referral_code, sponsor_id):
    try:
        email = email.lower().strip()
        phone = phone.strip()

        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO users
                (role_id, full_name, email, phone, password_hash, referral_code, sponsor_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (role_id, full_name, email, phone, password_hash, referral_code, sponsor_id))
            
            row = cur.fetchone()
            # FIX: Prevent TypeError if row is None (e.g. duplicate constraint violation)
            if not row:
                return None
                
            new_user_id = row['id'] if isinstance(row, dict) else row[0]

        logger.info(f"User created successfully: {email}")
        return new_user_id

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return None
