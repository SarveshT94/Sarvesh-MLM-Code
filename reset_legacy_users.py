from app.db import get_cursor
from app.utils.security import hash_password

def fix_legacy_passwords():
    # ⚠️ Type the emails of the existing users you want to fix here
    users_to_fix = [
        "suresh123@gmail.com",
        # "user2@gmail.com", 
        # "user3@gmail.com"
    ]
    
    # We will reset them all to this password so you can log in immediately
    universal_new_password = "Password123!"

    print("🔧 Starting Legacy Hash Repair...\n" + "="*40)

    for email in users_to_fix:
        try:
            clean_email = email.lower().strip()
            print(f"⏳ Generating new native bcrypt hash for: {clean_email}")
            
            # Use the NEW flawless security engine
            new_hash = hash_password(universal_new_password)
            
            with get_cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s 
                    WHERE email = %s
                    RETURNING id
                """, (new_hash, clean_email))
                
                updated_user = cur.fetchone()
                
                if updated_user:
                    print(f"✅ SUCCESS: {clean_email} is fixed!")
                else:
                    print(f"❌ ERROR: {clean_email} not found in the database. Check the spelling.")
                    
        except Exception as e:
            print(f"❌ SYSTEM ERROR for {email}: {str(e)}")

    print("\n🎉 Repair Complete! Go to your browser and log in with 'Password123!'")

if __name__ == "__main__":
    fix_legacy_passwords()
