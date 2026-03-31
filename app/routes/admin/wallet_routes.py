from flask import Blueprint, request, jsonify, session
from app.utils.auth import admin_required
from app.services.admin.wallet_force_service import force_wallet_adjust

admin_wallet_bp = Blueprint("admin_wallet", __name__)


@admin_wallet_bp.route("/admin/wallet/force-adjust", methods=["POST"])
@admin_required
def admin_wallet_adjust():

    data = request.get_json()

    user_id = data.get("user_id")
    amount = data.get("amount")
    action = data.get("action")
    remark = data.get("remark", "")

    if not user_id or not amount or not action:
        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    try:

        amount = float(amount)

        if amount <= 0:
            return jsonify({
                "success": False,
                "message": "Amount must be greater than zero"
            }), 400

        admin_id = session.get("user_id")

        result = force_wallet_adjust(
            user_id,
            amount,
            action,
            remark,
            admin_id
        )

        return jsonify({
            "success": True,
            "message": "Wallet adjusted successfully",
            "data": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
