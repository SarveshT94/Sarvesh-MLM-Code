from flask import Blueprint, jsonify
from app.utils.auth import admin_required
from app.services.admin.fraud_detection_service import get_fraud_report

admin_fraud_bp = Blueprint("admin_fraud", __name__)


@admin_fraud_bp.route("/admin/fraud/report", methods=["GET"])
@admin_required
def admin_fraud_report():

    try:

        report = get_fraud_report()

        return jsonify({
            "success": True,
            "data": report
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
