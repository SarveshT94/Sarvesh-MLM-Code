from flask import Blueprint, request, jsonify, session
from app.utils.auth import admin_required
from app.services.admin.commission_recalc_service import (
    recalc_user_commissions,
    recalc_purchase_commission,
    recalc_date_commissions,
    recalc_full_system
)

admin_commission_bp = Blueprint("admin_commission", __name__)


# ------------------------------------------------
# Recalculate commissions for a specific user
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-user", methods=["POST"])
@admin_required
def admin_recalculate_user_commission():

    data = request.get_json()

    user_id = data.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "message": "user_id required"
        }), 400

    try:

        admin_id = session.get("user_id")

        result = recalc_user_commissions(
            user_id,
            admin_id
        )

        return jsonify({
            "success": True,
            "message": "User commission recalculated",
            "data": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


# ------------------------------------------------
# Recalculate commission for a specific purchase
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-purchase", methods=["POST"])
@admin_required
def admin_recalculate_purchase_commission():

    data = request.get_json()

    purchase_id = data.get("purchase_id")

    if not purchase_id:
        return jsonify({
            "success": False,
            "message": "purchase_id required"
        }), 400

    try:

        admin_id = session.get("user_id")

        result = recalc_purchase_commission(
            purchase_id,
            admin_id
        )

        return jsonify({
            "success": True,
            "message": "Purchase commission recalculated",
            "data": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


# ------------------------------------------------
# Recalculate commissions for a specific date
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-date", methods=["POST"])
@admin_required
def admin_recalculate_date_commission():

    data = request.get_json()

    date = data.get("date")

    if not date:
        return jsonify({
            "success": False,
            "message": "date required"
        }), 400

    try:

        admin_id = session.get("user_id")

        result = recalc_date_commissions(
            date,
            admin_id
        )

        return jsonify({
            "success": True,
            "message": "Date commission recalculated",
            "data": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


# ------------------------------------------------
# Recalculate commissions for full system
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-system", methods=["POST"])
@admin_required
def admin_recalculate_system_commission():

    try:

        admin_id = session.get("user_id")

        result = recalc_full_system(admin_id)

        return jsonify({
            "success": True,
            "message": "Full system commission recalculated",
            "data": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
