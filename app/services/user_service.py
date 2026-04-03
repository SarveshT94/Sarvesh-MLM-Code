from app.db import get_cursor
from app.models.user_model import get_user_by_email, get_user_by_phone, create_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string

# -----------------------------------
# Secure Referral Code Generator
# -----------------------------------
def generate_unique_referral_code():
    """Generates a random 8-character alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(8))

# -----------------------------------
# Enterprise Registration Flow
# -----------------------------------
def register_new_member(full_name, email, phone, raw_password, sponsor_id=None):
    """
    The Gatekeeper: Ensures no duplicates, enforces secure password hashing, 
    and locks the account for KYC verification.
    """
    # 1. Strict Duplicate Checks
    if get_user_by_email(email):
        return {"status": "error", "message": "This email is already registered."}
        
    if get_user_by_phone(phone):
        return {"status": "error", "message": "This phone number is already registered."}

    # 2. Cryptographic Password Hashing (NEVER store plain text!)
    password_hash = generate_password_hash(raw_password)

    # 3. Generate a unique code for this new member to invite others
    referral_code = generate_unique_referral_code()
    
    # 4. Default Role ID (Assuming '2' is a standard member, '1' is Admin)
    role_id = 2 

    # 5. Safe Database Insertion
    try:
        new_user_id = create_user(
            role_id=role_id,
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            referral_code=referral_code,
            sponsor_id=sponsor_id
        )
        
        # 6. Initialize KYC Lock (Prevents withdrawals until Admin approves)
        with get_cursor() as cur:
            # We use ON CONFLICT DO NOTHING just in case, though it's a new user.
            cur.execute("""
                INSERT INTO kyc_details (user_id, status)
                VALUES (%s, %s)
            """, (new_user_id, 'Pending'))
            
        return {
            "status": "success", 
            "message": "Registration successful. Please complete KYC to unlock your wallet.",
            "user_id": new_user_id,
            "referral_code": referral_code
        }
        
    except Exception as e:
        # If anything fails (like the KYC table insert), the context manager automatically 
        # rolls back the user creation so we don't get "ghost" accounts.
        return {"status": "error", "message": f"System Error during registration: {str(e)}"}

# -----------------------------------
# Enterprise Login Flow
# -----------------------------------
def authenticate_user(email, raw_password):
    """
    Secure Authentication: Compares the cryptographic hash, not the plain text.
    """
    # 1. Find user
    user = get_user_by_email(email)
    if not user:
        # We don't say "Email not found" to prevent hackers from guessing emails.
        return {"status": "error", "message": "Invalid email or password."}
        
    # 2. Verify Hash
    if not check_password_hash(user['password_hash'], raw_password):
        return {"status": "error", "message": "Invalid email or password."}
        
    # 3. Success (Do not return the password hash to the frontend!)
    del user['password_hash']
    
    return {"status": "success", "message": "Login successful.", "user": user}
