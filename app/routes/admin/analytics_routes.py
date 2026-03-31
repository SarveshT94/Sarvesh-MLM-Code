from flask import Blueprint, jsonify
from app.utils.auth import admin_required
from app.services.admin.analytics_service import get_mlm_analytics

admin_analytics_bp = Blueprint("admin_analytics", __name__)


@admin_analytics_bp.route("/admin/analytics/dashboard", methods=["GET"])
@admin_required
def admin_analytics_dashboard():

    try:

        data = get_mlm_analytics()

        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
