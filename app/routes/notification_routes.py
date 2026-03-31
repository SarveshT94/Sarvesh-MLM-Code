from flask import Blueprint, jsonify, session
from app.utils.auth import login_required
from app.services.notification_service import (
    get_user_notifications,
    mark_notification_read
)

notification_bp = Blueprint("notification", __name__)


@notification_bp.route("/notifications", methods=["GET"])
@login_required
def user_notifications():

    user_id = session.get("user_id")

    data = get_user_notifications(user_id)

    return jsonify({
        "success": True,
        "data": data
    })


@notification_bp.route("/notifications/read/<int:notification_id>", methods=["POST"])
@login_required
def read_notification(notification_id):

    user_id = session.get("user_id")

    mark_notification_read(notification_id, user_id)

    return jsonify({
        "success": True,
        "message": "Notification marked as read"
    })
