from flask import Blueprint, jsonify
from app.utils.auth import admin_required
from app.services.admin.backup_service import (
    run_database_backup,
    get_backup_history
)

admin_backup_bp = Blueprint("admin_backup", __name__)


@admin_backup_bp.route("/admin/backup/run", methods=["POST"])
@admin_required
def run_backup():

    try:

        result = run_database_backup()

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@admin_backup_bp.route("/admin/backup/history", methods=["GET"])
@admin_required
def backup_history():

    data = get_backup_history()

    return jsonify({
        "success": True,
        "data": data
    })
