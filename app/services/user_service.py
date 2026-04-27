from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app.db import get_cursor
from app.models.user_model import get_user_by_email, get_user_by_phone, get_user_by_referral_code, create_user
from app.utils.security import hash_password, verify_password
import random
import string
import logging

logger = logging.getLogger(__name__)


# -----------------------------------
# Secure Token Generator Setup
# -----------------------------------
def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


# -----------------------------------
# Secure Referral Code Generator
# -----------------------------------
def generate_unique_referral_code(cur=None):
    chars = string.ascii_uppercase + string.digits

    def _generate(cur):
        while True:
            code = ''.join(random.choice(chars) for _ in range(8))
            cur.execute("SELECT id FROM users WHERE referral_code = %s", (code,))
            if not cur.fetchone():
                return code

    if cur:
        return _generate(cur)

    with get_cursor() as new_cur:
        return _generate(new_cur)


# -----------------------------------
# Enterprise Registration Flow
# -----------------------------------
def register_new_member(full_name, email, phone, raw_password, sponsor_id=None):
    try:
        email = email.lower().strip()
        phone = phone.strip()

        # 1. Duplicate Checks
        if get_user_by_email(email):
            return {"status": "error", "message": "This email is already registered."}

        if get_user_by_phone(phone):
            return {"status": "error", "message": "This phone number is already registered."}

        # 2. 🔥 FIX: Convert String Referral Code to Numeric User ID
        actual_sponsor_id = None
        if sponsor_id:
            sponsor = get_user_by_referral_code(sponsor_id)
            if not sponsor:
                return {"status": "error", "message": "Invalid Referral Code. Sponsor not found."}
            # Handle if the DB returns a RealDictRow or a Tuple
            actual_sponsor_id = sponsor['id'] if isinstance(sponsor, dict) else sponsor[0]

        password_hash = hash_password(raw_password)

        with get_cursor() as cur:
            # 3. Generate New Code
            referral_code = generate_unique_referral_code(cur)
            role_id = 2

            # 4. Create User (Passing the translated numeric ID!)
            new_user_id = create_user(
                role_id=role_id,
                full_name=full_name,
                email=email,
                phone=phone,
                password_hash=password_hash,
                referral_code=referral_code,
                sponsor_id=actual_sponsor_id
            )

            # 🔥 FIX: Stop the false success if the database write failed
            if not new_user_id:
                return {"status": "error", "message": "Database rejected the data. Registration failed."}

            # 5. Initialize KYC safely
            cur.execute("""
                INSERT INTO kyc_details (user_id, status)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (new_user_id, 'pending'))

        logger.info(f"User securely registered and committed: {email}")

        return {
            "status": "success",
            "message": "Registration successful. Please complete KYC.",
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
# Enterprise Login Flow (Email or Phone)
# -----------------------------------
def authenticate_user(identifier, raw_password):
    try:
        identifier = identifier.lower().strip()

        # 🚀 THE UPGRADE: Smart Routing
        if '@' in identifier:
            user = get_user_by_email(identifier)
        else:
            # If no '@', assume it's a phone number
            user = get_user_by_phone(identifier)

        if not user:
            return {"status": "error", "message": "Invalid credentials."}

        # 🔥 FIXED: Check if the Admin has deactivated this account
        if not user.get('is_active', True):
            logger.warning(f"Blocked login attempt for deactivated user: {identifier}")
            return {"status": "error", "message": "Your account has been deactivated. Please contact support."}

        # Strip invisible PostgreSQL padding spaces
        db_hash = user.get('password_hash', '')
        if isinstance(db_hash, str):
            db_hash = db_hash.strip()

        if not verify_password(db_hash, raw_password):
            logger.warning(f"Failed login attempt: {identifier}. Hash comparison failed.")
            return {"status": "error", "message": "Invalid credentials."}

        if 'password_hash' in user:
            del user['password_hash']

        logger.info(f"User authenticated: {identifier}")
        return {"status": "success", "message": "Login successful.", "user": user}

    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return {"status": "error", "message": "Internal server error"}

        
# -----------------------------------
# Forgot Password Flow (Email or Phone)
# -----------------------------------
def process_forgot_password(identifier):
    try:
        identifier = identifier.lower().strip()
        
        # 🚀 Smart Routing: Check if it's an email or a phone number
        if '@' in identifier:
            user = get_user_by_email(identifier)
        else:
            user = get_user_by_phone(identifier)

        success_message = {"status": "success", "message": "If that account exists, a password reset link has been sent."}

        if not user:
            return success_message

        # We always generate the token using their Email for backend consistency
        user_email = user['email']
        serializer = get_serializer()
        token = serializer.dumps(user_email, salt='password-reset-salt')
        
        reset_url = f"http://localhost:3000/reset-password?token={token}"
        
        logger.info(f"\n{'='*50}\n📧 SIMULATION: Reset link for {identifier}\n{reset_url}\n{'='*50}\n")
        
        return success_message

    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        return {"status": "error", "message": "Internal server error. Please try again later."}


# -----------------------------------
# Reset Password Flow
# -----------------------------------
def process_reset_password(token, new_password):
    try:
        serializer = get_serializer()
        try:
            # Unpack the email from the secure token (max age 1 hour)
            email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
        except SignatureExpired:
            return {"status": "error", "message": "The reset link has expired."}
        except BadSignature:
            return {"status": "error", "message": "Invalid reset link."}

        user = get_user_by_email(email)
        if not user:
            return {"status": "error", "message": "Account no longer exists."}

        new_hash = hash_password(new_password)

        with get_cursor() as cur:
            cur.execute("UPDATE users SET password_hash = %s WHERE email = %s", (new_hash, email))

        return {"status": "success", "message": "Your password has been successfully reset. You may now log in."}
    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        return {"status": "error", "message": "An error occurred while resetting your password."}

# -----------------------------------
# Admin Users Pagination
# -----------------------------------
def get_users_paginated(limit=50, offset=0):
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, full_name, email, phone, is_active, created_at
            FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s
        """, (limit, offset))
        return cur.fetchall()
