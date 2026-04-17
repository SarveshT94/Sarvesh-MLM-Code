from app.db import get_cursor

# -----------------------------------
# Submit KYC Documents (User Facing)
# -----------------------------------
def submit_kyc(user_id, pan_number=None, aadhar_number=None, bank_name=None, bank_account_no=None, bank_ifsc=None, document_type=None, document_number=None):
    """
    Allows a user to submit their KYC details.
    Bridged to support both your existing frontend and the new Enterprise Schema.
    """
    with get_cursor() as cur:
        # 1. Handle Legacy Frontend Submissions (if your frontend still sends document_type)
        if document_type and document_number:
            if 'PAN' in document_type.upper():
                pan_number = document_number
            else:
                aadhar_number = document_number

        # 2. Update the user's record directly (Enterprise Schema)
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'pending',
                pan_number = COALESCE(%s, pan_number),
                aadhar_number = COALESCE(%s, aadhar_number),
                bank_name = COALESCE(%s, bank_name),
                bank_account_no = COALESCE(%s, bank_account_no),
                bank_ifsc = COALESCE(%s, bank_ifsc),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (pan_number, aadhar_number, bank_name, bank_account_no, bank_ifsc, user_id))
        
        return {"status": "success", "message": "KYC submitted successfully. Pending Admin approval."}

# -----------------------------------
# Get Pending KYC Requests (Admin)
# -----------------------------------
def get_pending_kyc():
    """
    Fetches all users who have submitted full KYC & Bank Details 
    and are waiting for Admin approval.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, full_name, email, phone, 
                   pan_number, aadhar_number, 
                   bank_name, bank_account_no, bank_ifsc,
                   kyc_status, created_at
            FROM users 
            WHERE kyc_status = 'pending'
            ORDER BY created_at ASC
        """)
        return cur.fetchall()

# -----------------------------------
# Approve KYC Request (Admin)
# -----------------------------------
def approve_kyc(user_id, admin_id):
    """
    Marks a user as verified. This unlocks their ability to request withdrawals.
    """
    with get_cursor() as cur:
        # 1. Lock the row to prevent race conditions
        cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        
        # 2. Update to Approved
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'approved', 
                kyc_rejection_reason = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user_id,))
        
        return {"status": "success", "message": f"KYC for User #{user_id} Approved. Withdrawals unlocked."}

# -----------------------------------
# Reject KYC Request (Admin)
# -----------------------------------
def reject_kyc(user_id, admin_id, reason):
    """
    Rejects the KYC, logs the exact reason, and notifies the user to fix it.
    """
    with get_cursor() as cur:
        # 1. Lock the row
        cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        
        # 2. Update to Rejected and save the reason
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'rejected', 
                kyc_rejection_reason = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (reason, user_id))
        
        # 3. Log notification for the user (Fails safely if table doesn't exist yet)
        try:
            cur.execute("""
                INSERT INTO notifications (user_id, title, message)
                VALUES (%s, %s, %s)
            """, (user_id, "KYC Rejected", f"Your KYC was rejected. Reason: {reason}. Please re-submit."))
        except Exception as e:
            print(f"Notice: Notification skipped. Ensure notifications table exists. {e}")
            
        return {"status": "success", "message": f"KYC Rejected safely. Reason: {reason}"}
