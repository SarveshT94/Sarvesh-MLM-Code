from flask import Blueprint, jsonify
from app.utils.auth import admin_required
from app.db import get_cursor

admin_cron_bp = Blueprint("admin_cron", __name__)


@admin_cron_bp.route("/admin/cron/status", methods=["GET"])
@admin_required
def get_cron_status():

    cursor = get_cursor()

    cursor.execute("""
        SELECT job_name, status, message, executed_at
        FROM cron_job_logs
        ORDER BY executed_at DESC
        LIMIT 50
    """)

    logs = cursor.fetchall()

    return jsonify({
        "success": True,
        "data": logs
    })
