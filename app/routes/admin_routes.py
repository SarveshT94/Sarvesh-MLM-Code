from flask import Blueprint, render_template, request, jsonify, session
from app.services.payout_service import get_payout_report
from app.services.user_service import get_users_paginated
from app.services.epin_service import generate_epins  # Ensure this import exists
from app.utils.decorators import login_required      # Assuming your decorator is here
from app.services.admin_system_service import get_system_health
from flask import request, redirect
from app.services.admin_wallet_service import admin_wallet_adjust


# Define the blueprint
admin = Blueprint("admin", __name__, url_prefix="/admin")

@admin.route("/generate-epins", methods=["POST"])
@login_required
def generate_epins_api():
    """
    API endpoint to generate E-Pins. 
    Expects JSON: { "package_id": int, "amount": float, "quantity": int }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    # Production Check: Use .get() to prevent KeyErrors if session is cleared
    admin_id = session.get("user_id")
    if not admin_id:
        return jsonify({"error": "Unauthorized"}), 401

    package_id = data.get("package_id")
    amount = data.get("amount")
    quantity = data.get("quantity")

    # Validation: Ensure we aren't passing None to the service
    if not all([package_id, amount, quantity]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        result = generate_epins(
            admin_id=admin_id,
            package_id=package_id,
            amount=amount,
            quantity=quantity
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin.route("/payout-report", methods=["GET"])
@login_required
def payout_report():
    """Returns the generated payout report data."""
    try:
        result = get_payout_report()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch report"}), 500


@admin.route("/users")
@login_required
def admin_users_page():
    """Renders the user management dashboard."""
    return render_template("admin/users.html")


@admin.route("/api/users")
@login_required
def admin_users_api():
    """Paginated API for the user management table."""
    try:
        # Default to page 1, ensure it's an integer
        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "")

        data = get_users_paginated(page=page, search=search)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": "Data retrieval failed"}), 500


@admin.route("/user/<int:user_id>")
@login_required
def admin_user_profile(user_id):
    """Renders a specific user's profile for administrative review."""

    from app.services.user_service import get_user_profile

    user = get_user_profile(user_id)

    return render_template(
        "admin/user_profile.html",
        user=user
    )

@admin.route("/admin/system-health")
def system_health():

    stats = get_system_health()

    return render_template(
        "admin/system_health.html",
        stats=stats
    )


@admin.route("/admin/wallet-adjust", methods=["POST"])
def wallet_adjust():

    user_id = request.form["user_id"]
    amount = request.form["amount"]
    remark = request.form["remark"]

    admin_wallet_adjust(user_id, amount, remark)

    return redirect("/admin/users")
