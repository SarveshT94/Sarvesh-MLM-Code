from flask import Blueprint, request, jsonify, session
from app.utils.auth import admin_required
from app.services.support_service import reply_ticket

admin_support_bp = Blueprint("admin_support", __name__)


@admin_support_bp.route("/admin/support/reply/<int:ticket_id>", methods=["POST"])
@admin_required
def admin_reply_ticket(ticket_id):

    data = request.get_json()

    message = data.get("message")

    admin_id = session.get("user_id")

    reply_ticket(ticket_id, admin_id, "admin", message)

    return jsonify({
        "success": True,
        "message": "Reply sent"
    })
