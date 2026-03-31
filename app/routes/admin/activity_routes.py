from flask import Blueprint, jsonify
from app.utils.auth import admin_required
from app.db import get_cursor

admin_activity_bp = Blueprint("admin_activity", __name__)


@admin_activity_bp.route("/admin/activity/logs", methods=["GET"])
@admin_required
def get_admin_activity_logs():

    cursor = get_cursor()

    cursor.execute("""
        SELECT *
        FROM admin_activity_logs
        ORDER BY created_at DESC
        LIMIT 100
    """)

    logs = cursor.fetchall()

    return jsonify({
        "success": True,
        "data": logs
    })
