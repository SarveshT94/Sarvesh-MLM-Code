from app.db import get_cursor


def submit_kyc(user_id, doc_type, doc_number, doc_img, selfie_img):

    with get_cursor() as cur:

        cur.execute("""
            INSERT INTO kyc_requests
            (user_id, document_type, document_number, document_image, selfie_image)
            VALUES (%s,%s,%s,%s,%s)
        """, (user_id, doc_type, doc_number, doc_img, selfie_img))

    return True


def get_pending_kyc():

    with get_cursor() as cur:

        cur.execute("""
            SELECT
                k.id,
                k.user_id,
                u.full_name,
                k.document_type,
                k.document_number,
                k.document_image,
                k.selfie_image,
                k.status,
                k.submitted_at
            FROM kyc_requests k
            JOIN users u ON u.id = k.user_id
            WHERE k.status='pending'
            ORDER BY k.submitted_at ASC
        """)

        return cur.fetchall()


def approve_kyc(kyc_id):

    with get_cursor() as cur:

        cur.execute("""
            UPDATE kyc_requests
            SET status='approved',
                reviewed_at=NOW()
            WHERE id=%s
        """, (kyc_id,))

    return True


def reject_kyc(kyc_id, note):

    with get_cursor() as cur:

        cur.execute("""
            UPDATE kyc_requests
            SET status='rejected',
                admin_note=%s,
                reviewed_at=NOW()
            WHERE id=%s
        """, (note, kyc_id))

    return True
