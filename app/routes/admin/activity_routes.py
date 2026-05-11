from flask import Blueprint, jsonify, request
from app.utils.auth import admin_required
from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)
admin_activity_bp = Blueprint("admin_activity", __name__)


@admin_activity_bp.route("/admin/activity/logs", methods=["GET"])
@admin_required
def get_admin_activity_logs():
    """
    BUG FIXED #7:
    Was using cursor = get_cursor() directly — crashes.
    Fixed to use `with get_cursor() as cur:` pattern.
    """
    try:
        limit  = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        with get_cursor() as cur:
            cur.execute("""
                SELECT *
                FROM audit_logs
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            logs = cur.fetchall()

        return jsonify({"success": True, "data": logs})

    except Exception as e:
        logger.error(f"Activity logs error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
