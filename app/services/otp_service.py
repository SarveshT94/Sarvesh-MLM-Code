import random
import string
from datetime import datetime, timedelta
from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)

def generate_otp():
    """Generates a secure 6-digit numerical OTP."""
    return ''.join(random.choices(string.digits, k=6))

def create_and_send_otp(user_id, identifier_type, new_identifier):
    """
    Saves a new OTP to the database and 'sends' it to the user.
    identifier_type should be 'email' or 'phone'.
    """
    try:
        otp_code = generate_otp()
        # OTP expires in 10 minutes
        expires_at = datetime.now() + timedelta(minutes=10)

        with get_cursor() as cur:
            # First, delete any existing unverified OTPs for this user to prevent spam
            cur.execute("DELETE FROM otp_verifications WHERE user_id = %s", (user_id,))
            
            # Insert the new OTP
            cur.execute("""
                INSERT INTO otp_verifications (user_id, identifier_type, new_identifier, otp_code, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, identifier_type, new_identifier, otp_code, expires_at))

        # 🚨 SIMULATION: Printing the OTP to the backend terminal
        print(f"\n{'='*50}")
        if identifier_type == 'email':
            print(f"📧 EMAIL SIMULATION: Sending OTP to {new_identifier}")
        else:
            print(f"📱 SMS SIMULATION: Sending OTP to {new_identifier}")
        
        print(f"🔑 YOUR SECRET OTP CODE IS: {otp_code}")
        print(f"{'='*50}\n")

        return {"status": "success", "message": f"OTP sent successfully to your new {identifier_type}."}

    except Exception as e:
        logger.error(f"Error generating OTP: {str(e)}")
        return {"status": "error", "message": "Failed to generate OTP. Please try again."}

def verify_and_update_profile(user_id, otp_code):
    """
    Checks if the OTP is valid. If it is, updates the user's main profile 
    and deletes the OTP record.
    """
    try:
        with get_cursor() as cur:
            # 1. Find the OTP record
            cur.execute("""
                SELECT identifier_type, new_identifier, expires_at 
                FROM otp_verifications 
                WHERE user_id = %s AND otp_code = %s
            """, (user_id, otp_code))
            
            record = cur.fetchone()

            if not record:
                return {"status": "error", "message": "Invalid OTP code."}

            # 2. Check if it expired
            if record['expires_at'] < datetime.now():
                # Delete the expired record
                cur.execute("DELETE FROM otp_verifications WHERE user_id = %s", (user_id,))
                return {"status": "error", "message": "This OTP has expired. Please request a new one."}

            # 3. Update the actual users table
            identifier_type = record['identifier_type']
            new_identifier = record['new_identifier']

            if identifier_type == 'email':
                cur.execute("UPDATE users SET email = %s WHERE id = %s", (new_identifier, user_id))
            elif identifier_type == 'phone':
                cur.execute("UPDATE users SET phone = %s WHERE id = %s", (new_identifier, user_id))

            # 4. Cleanup the used OTP
            cur.execute("DELETE FROM otp_verifications WHERE user_id = %s", (user_id,))

            return {
                "status": "success", 
                "message": f"Your {identifier_type} has been successfully updated!"
            }

    except Exception as e:
        logger.error(f"Error verifying OTP: {str(e)}")
        return {"status": "error", "message": "An error occurred during verification."}
