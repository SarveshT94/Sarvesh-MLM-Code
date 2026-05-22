"""
app/routes/admin/report_routes.py
==================================
API endpoints that serve audit drill-down data and CSV exports.
"""

from flask import Blueprint, jsonify, Response
from app.utils.auth import admin_required
from app.services.report_service import (
    get_revenue_audit,
    get_gross_profit_audit,
    get_net_profit_audit,
    get_admin_fees_audit,
    get_tds_audit,
    get_liability_audit,
)
import logging
import csv
from io import StringIO
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)

# Create the blueprint – this is the name you import
admin_report_bp = Blueprint("admin_report", __name__)


def _serialize(rows):
    """Convert rows to JSON-serializable dicts."""
    if not rows:
        return []
    result = []
    for row in rows:
        d = {}
        # Convert to dict if it's a RealDictRow or similar
        items = dict(row).items() if hasattr(row, 'items') else row.items()
        for k, v in items:
            if isinstance(v, (datetime, date)):
                d[k] = v.isoformat()
            elif isinstance(v, Decimal):
                d[k] = float(v)
            else:
                d[k] = v
        result.append(d)
    return result


# =========================================================
# WEB TABLE ENDPOINTS (Feeds the HTML Modal)
# =========================================================

@admin_report_bp.route("/audit/revenue")
@admin_required
def audit_revenue():
    try:
        data = get_revenue_audit()
        return jsonify({"success": True, "data": _serialize(data)})
    except Exception as e:
        logger.error(f"Revenue audit error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load revenue data"}), 500


@admin_report_bp.route("/audit/gross-profit")
@admin_required
def audit_gross_profit():
    try:
        data = get_gross_profit_audit()
        return jsonify({"success": True, "data": _serialize(data)})
    except Exception as e:
        logger.error(f"Gross profit audit error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load gross profit data"}), 500


@admin_report_bp.route("/audit/net-profit")
@admin_required
def audit_net_profit():
    try:
        data = get_net_profit_audit()
        return jsonify({
            "success": True,
            "recent": _serialize(data["recent"]),
            "total_records": data.get("total_records", len(data["recent"]))
        })
    except Exception as e:
        logger.error(f"Net profit audit error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load net profit data"}), 500


@admin_report_bp.route("/audit/admin-fees")
@admin_required
def audit_admin_fees():
    try:
        data = get_admin_fees_audit()
        return jsonify({"success": True, "data": _serialize(data)})
    except Exception as e:
        logger.error(f"Admin fees audit error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load admin fees data"}), 500


@admin_report_bp.route("/audit/tds")
@admin_required
def audit_tds():
    try:
        data = get_tds_audit()
        return jsonify({"success": True, "data": _serialize(data)})
    except Exception as e:
        logger.error(f"TDS audit error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load TDS data"}), 500


@admin_report_bp.route("/audit/liability")
@admin_required
def audit_liability():
    try:
        data = get_liability_audit()
        return jsonify({"success": True, "data": _serialize(data)})
    except Exception as e:
        logger.error(f"Liability audit error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load liability data"}), 500


# =========================================================
# EXCEL (CSV) EXPORT ENDPOINT
# =========================================================

@admin_report_bp.route("/export/<report_type>")
@admin_required
def export_excel(report_type):
    try:
        if report_type == "revenue":
            data = get_revenue_audit()
        elif report_type == "gross":
            data = get_gross_profit_audit()
        elif report_type == "net":
            net_data = get_net_profit_audit()
            data = net_data["recent"]
        elif report_type == "admin_fees":
            data = get_admin_fees_audit()
        elif report_type == "tds":
            data = get_tds_audit()
        elif report_type == "liability":
            data = get_liability_audit()
        else:
            return jsonify({"success": False, "message": "Invalid report type"}), 400

        serialized_data = _serialize(data)
        if not serialized_data:
            serialized_data = [{"Notice": "No records found for this period."}]

        output = StringIO()
        headers = list(serialized_data[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(serialized_data)

        csv_content = output.getvalue()
        filename = f"{report_type}_audit.csv"
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        logger.error(f"CSV export error for {report_type}: {str(e)}")
        return jsonify({"success": False, "message": "Failed to generate file."}), 500
