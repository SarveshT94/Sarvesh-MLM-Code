from app.db import get_cursor

# -----------------------------------
# Submit KYC Documents (User Facing)
# -----------------------------------
def submit_kyc(user_id, document_type, document_number):
    """
    Allows a user to submit their KYC details (PAN/Aadhaar) for review.
    Uses an UPSERT (Insert or Update) so if they are rejected and try again, 
    it updates their existing record instead of crashing the database.
    """
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO kyc_details (user_id, document_type, document_number, status)
            VALUES (%s, %s, %s, 'Pending')
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                document_type = EXCLUDED.document_type,
                document_number = EXCLUDED.document_number,
                status = 'Pending',
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, document_type, document_number))
        
        return {"status": "success", "message": "KYC submitted successfully. Pending Admin approval."}

# -----------------------------------
# Get Pending KYC Requests (Admin Facing)
# -----------------------------------
def get_pending_kyc():
    """
    Fetches all users who are waiting for KYC approval.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT k.id, k.user_id, u.full_name, u.email, k.document_type, k.document_number, k.created_at
            FROM kyc_details k
            JOIN users u ON k.user_id = u.id
            WHERE k.status = 'Pending'
            ORDER BY k.created_at ASC
        """)
        return cur.fetchall()

# -----------------------------------
# Approve KYC Request (Admin Control)
# -----------------------------------
def approve_kyc(kyc_id, admin_id):
    """
    Unlocks the user's account so they can withdraw their commissions.
    """
    with get_cursor() as cur:
        # 1. Lock the row to prevent double-approvals
        cur.execute("SELECT * FROM kyc_details WHERE id = %s FOR UPDATE", (kyc_id,))
        kyc_record = cur.fetchone()

        if not kyc_record or kyc_record['status'] != 'Pending':
            return {"status": "error", "message": "KYC record not found or already processed."}

        # 2. Update to Verified
        cur.execute("""
            UPDATE kyc_details 
            SET status = 'Verified', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (kyc_id,))
        
        return {"status": "success", "message": "KYC Approved. User account is now unlocked."}

# -----------------------------------
# Reject KYC Request (Admin Control)
# -----------------------------------
def reject_kyc(kyc_id, admin_id, reason):
    """
    Rejects the KYC and forces the user to re-submit with the correct documents.
    """
    with get_cursor() as cur:
        # 1. Lock the row
        cur.execute("SELECT * FROM kyc_details WHERE id = %s FOR UPDATE", (kyc_id,))
        kyc_record = cur.fetchone()

        if not kyc_record or kyc_record['status'] != 'Pending':
            return {"status": "error", "message": "KYC record not found or already processed."}

        # 2. Update to Rejected
        cur.execute("""
            UPDATE kyc_details 
            SET status = 'Rejected', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (kyc_id,))
        
        # 3. Log the reason so the user can see what they did wrong
        # (Assuming you have a notifications table, we insert an alert for the user here)
        cur.execute("""
            INSERT INTO notifications (user_id, title, message)
            VALUES (%s, %s, %s)
        """, (
            kyc_record['user_id'], 
            "KYC Rejected", 
            f"Your KYC was rejected. Reason: {reason}. Please re-submit."
        ))
        
        return {"status": "success", "message": f"KYC Rejected safely. User notified with reason: {reason}"}
