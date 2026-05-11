from flask import Blueprint, jsonify
from app.utils.auth import admin_required
from app.services.cron_monitor_service import get_cron_logs
import logging

logger = logging.getLogger(__name__)
admin_cron_bp = Blueprint("admin_cron", __name__)


@admin_cron_bp.route("/admin/cron/status", methods=["GET"])
@admin_required
def get_cron_status():
    """
    BUG FIXED #8:
    Was using cursor = get_cursor() directly in cron_monitor_service — crashes.
    Now delegates to get_cron_logs() which uses the correct pattern.
    """
    try:
        logs = get_cron_logs(limit=50)
        return jsonify({"success": True, "data": logs})
    except Exception as e:
        logger.error(f"Cron status error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
