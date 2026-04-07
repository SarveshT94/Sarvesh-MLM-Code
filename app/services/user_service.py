from app.db import get_cursor
from app.models.user_model import get_user_by_email, get_user_by_phone, create_user
from app.utils.security import hash_password, verify_password
import random
import string
import logging

logger = logging.getLogger(__name__)

# -----------------------------------
# Secure Referral Code Generator
# -----------------------------------
def generate_unique_referral_code():
    """Generates a UNIQUE 8-character referral code."""
    chars = string.ascii_uppercase + string.digits

    while True:
        code = ''.join(random.choice(chars) for _ in range(8))

        # Ensure uniqueness
        with get_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE referral_code = %s", (code,))
            if not cur.fetchone():
                return code


# -----------------------------------
# Enterprise Registration Flow
# -----------------------------------
def register_new_member(full_name, email, phone, raw_password, sponsor_id=None):
    try:
        # ✅ Normalize input
        email = email.lower().strip()
        phone = phone.strip()

        # 1. Duplicate Checks
        if get_user_by_email(email):
            return {"status": "error", "message": "This email is already registered."}

        if get_user_by_phone(phone):
            return {"status": "error", "message": "This phone number is already registered."}

        # 2. Secure Password Hashing (bcrypt)
        password_hash = hash_password(raw_password)

        # 3. Unique Referral Code
        referral_code = generate_unique_referral_code()

        # 4. Default Role
        role_id = 2

        # 5. Create User
        new_user_id = create_user(
            role_id=role_id,
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            referral_code=referral_code,
            sponsor_id=sponsor_id
        )

        # 6. Initialize KYC
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO kyc_details (user_id, status)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (new_user_id, 'Pending'))

        logger.info(f"User registered: {email}")

        return {
            "status": "success",
            "message": "Registration successful. Please complete KYC to unlock your wallet.",
            "user_id": new_user_id,
            "referral_code": referral_code
        }

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return {
            "status": "error",
            "message": "System error during registration"
        }


# -----------------------------------
# Enterprise Login Flow
# -----------------------------------
def authenticate_user(email, raw_password):
    try:
        email = email.lower().strip()

        # 1. Find user
        user = get_user_by_email(email)
        if not user:
            return {"status": "error", "message": "Invalid email or password."}

        # 2. Verify Password (bcrypt + fallback)
        if not verify_password(user['password_hash'], raw_password):
            logger.warning(f"Failed login attempt: {email}")
            return {"status": "error", "message": "Invalid email or password."}

        # 3. Remove sensitive data
        user.pop('password_hash', None)

        logger.info(f"User authenticated: {email}")

        return {
            "status": "success",
            "message": "Login successful.",
            "user": user
        }

    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return {
            "status": "error",
            "message": "Internal server error"
        }
