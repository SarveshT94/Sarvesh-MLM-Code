from flask import Blueprint, request, jsonify, session
from app.utils.auth import login_required
from app.services.support_service import (
    create_ticket,
    reply_ticket,
    get_ticket_messages
)

support_bp = Blueprint("support", __name__)


@support_bp.route("/support/create", methods=["POST"])
@login_required
def create_support_ticket():

    data = request.get_json()

    subject = data.get("subject")
    message = data.get("message")

    if not subject or not message:
        return jsonify({
            "success": False,
            "message": "subject and message required"
        }), 400

    user_id = session.get("user_id")

    ticket_id = create_ticket(user_id, subject, message)

    return jsonify({
        "success": True,
        "ticket_id": ticket_id
    })


@support_bp.route("/support/ticket/<int:ticket_id>", methods=["GET"])
@login_required
def get_ticket(ticket_id):

    data = get_ticket_messages(ticket_id)

    return jsonify({
        "success": True,
        "messages": data
    })


@support_bp.route("/support/reply/<int:ticket_id>", methods=["POST"])
@login_required
def reply_support(ticket_id):

    data = request.get_json()

    message = data.get("message")

    user_id = session.get("user_id")

    reply_ticket(ticket_id, user_id, "user", message)

    return jsonify({
        "success": True
    })
