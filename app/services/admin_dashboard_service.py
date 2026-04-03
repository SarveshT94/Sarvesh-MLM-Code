from app.db import get_cursor
from decimal import Decimal

# -----------------------------------
# System Health & Analytics Dashboard
# -----------------------------------
def get_dashboard_stats():
    """
    Enterprise Analytics Engine:
    Gathers all vital company metrics in highly optimized, safe queries.
    Uses COALESCE to prevent crashes if the database is brand new and empty.
    """
    stats = {
        "total_users": 0,
        "total_commissions_paid": Decimal('0.00'),
        "pending_payout_count": 0,
        "pending_payout_amount": Decimal('0.00'),
        "pending_kyc_count": 0
    }

    with get_cursor() as cur:
        # 1. Total Active Members (Assuming role_id 2 = Member)
        cur.execute("SELECT COUNT(*) as total_users FROM users WHERE role_id = 2")
        stats["total_users"] = cur.fetchone()['total_users']

        # 2. Total Money Paid Out (Summing the Ledger)
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_paid 
            FROM wallet_ledger 
            WHERE transaction_type = 'commission_credit'
        """)
        stats["total_commissions_paid"] = Decimal(str(cur.fetchone()['total_paid']))

        # 3. Pending Financial Liabilities (Money waiting to be approved)
        cur.execute("""
            SELECT 
                COUNT(*) as payout_count, 
                COALESCE(SUM(amount), 0) as payout_amount 
            FROM withdraw_requests 
            WHERE status = 'Pending'
        """)
        payout_data = cur.fetchone()
        stats["pending_payout_count"] = payout_data['payout_count']
        stats["pending_payout_amount"] = Decimal(str(payout_data['payout_amount']))

        # 4. Gatekeeper Queue (Users waiting for KYC Approval)
        cur.execute("SELECT COUNT(*) as pending_kyc FROM kyc_details WHERE status = 'Pending'")
        stats["pending_kyc_count"] = cur.fetchone()['pending_kyc']

        return stats
