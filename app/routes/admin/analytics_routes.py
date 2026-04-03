from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.services.admin_dashboard_service import get_dashboard_stats

# Create the Blueprint matching the exact name we registered in __init__.py
admin_analytics_bp = Blueprint('admin_analytics', __name__)

# -----------------------------------
# Core Dashboard Analytics Endpoint
# -----------------------------------
@admin_analytics_bp.route('/dashboard-stats', methods=['GET'])
@login_required
def dashboard_stats():
    """
    Enterprise API: Fetches real-time system health metrics.
    Endpoint: GET /api/admin/analytics/dashboard-stats
    Security: Strictly locked down to Admin users.
    """
    # 1. The Vault Check: Ensure only Admins can view company financials.
    # (Assuming role_id 1 = Admin, and role_id 2 = Standard Member)
    if current_user.role_id != 1:
        return jsonify({
            "status": "error", 
            "message": "Unauthorized. Admin privileges required to view company financials."
        }), 403

    try:
        # 2. Fetch the highly optimized data from the Service layer (Step 10)
        stats = get_dashboard_stats()
        
        # 3. Return the payload to the frontend React/Admin Dashboard
        return jsonify({
            "status": "success",
            "message": "Dashboard analytics retrieved successfully.",
            "data": stats
        }), 200

    except Exception as e:
        # 4. Graceful Error Handling: Prevent the API from crashing 
        # if the database momentarily disconnects.
        return jsonify({
            "status": "error", 
            "message": "System Error: Unable to load analytics."
        }), 500
