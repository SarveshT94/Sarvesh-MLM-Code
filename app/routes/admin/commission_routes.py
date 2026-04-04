from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

# Import your excellent Time Machine / Recalc Services
from app.services.admin.commission_recalc_service import (
    recalc_user_commissions,
    recalc_purchase_commission,
    recalc_date_commissions,
    recalc_full_system
)

admin_commission_bp = Blueprint("admin_commission", __name__)

# --- Enterprise Security Helper ---
def is_admin():
    """Instantly blocks non-admin users from triggering recalculations."""
    return current_user.is_authenticated and getattr(current_user, 'role_id', None) == 1


# ------------------------------------------------
# Recalculate commissions for a specific user
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-user", methods=["POST"])
@login_required
def admin_recalculate_user_commission():
    if not is_admin(): 
        return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "user_id required"}), 400

    try:
        # Securely pull the Admin ID from the locked session, not the raw cookie
        result = recalc_user_commissions(user_id, current_user.id)
        
        return jsonify({
            "success": True,
            "message": "User commission recalculated",
            "data": result
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ------------------------------------------------
# Recalculate commission for a specific purchase
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-purchase", methods=["POST"])
@login_required
def admin_recalculate_purchase_commission():
    if not is_admin(): 
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.get_json()
    purchase_id = data.get("purchase_id")

    if not purchase_id:
        return jsonify({"success": False, "message": "purchase_id required"}), 400

    try:
        result = recalc_purchase_commission(purchase_id, current_user.id)
        
        return jsonify({
            "success": True,
            "message": "Purchase commission recalculated",
            "data": result
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ------------------------------------------------
# Recalculate commissions for a specific date
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-date", methods=["POST"])
@login_required
def admin_recalculate_date_commission():
    if not is_admin(): 
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.get_json()
    date = data.get("date")

    if not date:
        return jsonify({"success": False, "message": "date required"}), 400

    try:
        result = recalc_date_commissions(date, current_user.id)
        
        return jsonify({
            "success": True,
            "message": "Date commission recalculated",
            "data": result
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ------------------------------------------------
# Recalculate commissions for full system
# ------------------------------------------------
@admin_commission_bp.route("/admin/commission/recalculate-system", methods=["POST"])
@login_required
def admin_recalculate_system_commission():
    if not is_admin(): 
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        result = recalc_full_system(current_user.id)
        
        return jsonify({
            "success": True,
            "message": "Full system commission recalculated",
            "data": result
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
