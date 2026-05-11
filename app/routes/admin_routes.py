from flask import Blueprint, render_template, request, jsonify, session, redirect
from flask_login import login_required, current_user

from app.services.payout_service import get_payout_report
from app.services.user_service import get_users_paginated
from app.services.epin_service import generate_epins
from app.services.admin_system_service import get_system_health
from app.services.admin_wallet_service import (
    admin_wallet_adjust, get_pending_withdrawals,
    approve_withdrawal, reject_withdrawal
)
from app.services.kyc_service import get_pending_kyc, approve_kyc, reject_kyc
# BUG FIXED #12: create_package and deactivate_package were used in routes but never imported.
from app.services.package_service import (
    get_all_active_packages, get_all_plans,
    create_plan as create_package,
    update_plan
)
import logging

logger = logging.getLogger(__name__)
admin = Blueprint("admin", __name__)


def is_admin():
    return current_user.is_authenticated and getattr(current_user, 'role_id', None) == 1


@admin.route("/generate-epins", methods=["POST"])
@login_required
def generate_epins_api():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    admin_id  = session.get("user_id")
    if not admin_id:
        return jsonify({"error": "Unauthorized"}), 401
    package_id = data.get("package_id")
    amount     = data.get("amount")
    quantity   = data.get("quantity")
    if not all([package_id, amount, quantity]):
        return jsonify({"error": "Missing required fields"}), 400
    try:
        result = generate_epins(admin_id=admin_id, package_id=package_id,
                                amount=amount, quantity=quantity)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin.route("/payout-report", methods=["GET"])
@login_required
def payout_report():
    try:
        result = get_payout_report()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch report"}), 500


@admin.route("/users")
@login_required
def admin_users_page():
    return render_template("admin/users.html")


@admin.route("/api/users")
@login_required
def admin_users_api():
    try:
        page   = request.args.get("page", 1, type=int)
        search = request.args.get("search", "")
        data   = get_users_paginated(page=page, search=search)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": "Data retrieval failed"}), 500


@admin.route("/admin/system-health")
@login_required
def system_health():
    stats = get_system_health()
    return render_template("admin/system_health.html", stats=stats)


@admin.route("/admin/wallet-adjust", methods=["POST"])
@login_required
def wallet_adjust():
    """
    BUG FIXED #24:
    Old code called admin_wallet_adjust(user_id, amount, remark) with wrong args.
    The function signature is admin_wallet_adjust(user_id, amount, action, admin_id, remark="").
    Fixed: now reads 'action' from the form and passes admin_id from session.
    """
    if not is_admin():
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    user_id  = request.form.get("user_id")
    amount   = request.form.get("amount")
    action   = request.form.get("action", "credit")   # FIXED: was missing
    remark   = request.form.get("remark", "")
    admin_id = session.get("user_id")                 # FIXED: was missing
    try:
        result = admin_wallet_adjust(user_id, float(amount), action, admin_id, remark)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# KYC routes
@admin.route('/kyc/pending', methods=['GET'])
@login_required
def fetch_pending_kyc():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        return jsonify({"status": "success", "data": get_pending_kyc()}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@admin.route('/kyc/approve/<int:kyc_id>', methods=['POST'])
@login_required
def process_kyc_approval(kyc_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        result = approve_kyc(kyc_id, current_user.id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@admin.route('/kyc/reject/<int:kyc_id>', methods=['POST'])
@login_required
def process_kyc_rejection(kyc_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    data = request.get_json()
    if not data or not data.get('reason'):
        return jsonify({"status": "error", "message": "Rejection reason required"}), 400
    try:
        result = reject_kyc(kyc_id, current_user.id, data.get('reason'))
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Withdrawal routes
@admin.route('/admin/withdraws', methods=['GET'])
@login_required
def manage_withdrawals():
    if not is_admin(): return redirect("/")
    try:
        pending_requests = get_pending_withdrawals()
        return render_template("admin/withdraw_requests.html", requests=pending_requests)
    except Exception as e:
        return f"System Error: {str(e)}"


@admin.route('/payouts/approve/<int:request_id>', methods=['POST', 'GET'])
@login_required
def process_payout_approval(request_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        approve_withdrawal(request_id, current_user.id)
        return redirect("/admin/withdraws")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@admin.route('/payouts/reject/<int:request_id>', methods=['POST'])
@login_required
def process_payout_rejection(request_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    reason = request.form.get('reason', 'Violation of terms or invalid bank details.')
    try:
        reject_withdrawal(request_id, current_user.id, reason)
        return redirect("/admin/withdraws")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Package routes — FIXED: create_package and deactivate_package now imported
@admin.route('/packages', methods=['GET'])
@login_required
def fetch_packages():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        return jsonify({"status": "success", "data": get_all_active_packages()}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@admin.route('/packages/create', methods=['POST'])
@login_required
def create_new_package():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    data = request.get_json()
    if not data or not all(f in data for f in ['name', 'price']):
        return jsonify({"status": "error", "message": "Missing package details"}), 400
    try:
        pkg_id = create_package(name=data['name'], price=data['price'],
                                coupons=data.get('coupons', 12))
        return jsonify({"status": "success", "package_id": pkg_id}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@admin.route('/packages/<int:package_id>/deactivate', methods=['POST'])
@login_required
def retire_package(package_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        update_plan(package_id, price=None, coupons=None, is_active=False)
        return jsonify({"status": "success", "message": "Package deactivated"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
