from flask import Blueprint, render_template, request, jsonify, session, redirect
from flask_login import login_required, current_user

# --- Existing Service Imports ---
from app.services.payout_service import get_payout_report
from app.services.user_service import get_users_paginated
from app.services.epin_service import generate_epins  
from app.services.admin_system_service import get_system_health
from app.services.admin_wallet_service import admin_wallet_adjust

# --- Enterprise Service Imports ---
from app.services.kyc_service import get_pending_kyc, approve_kyc, reject_kyc
from app.services.admin_wallet_service import get_pending_withdrawals, approve_withdrawal, reject_withdrawal
from app.services.package_service import create_package, get_all_active_packages, deactivate_package

# Define the blueprint
admin = Blueprint("admin", __name__)

# ==========================================
# 🛑 EXISTING LEGACY ROUTES (Preserved)
# ==========================================

@admin.route("/generate-epins", methods=["POST"])
@login_required
def generate_epins_api():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    admin_id = session.get("user_id")
    if not admin_id:
        return jsonify({"error": "Unauthorized"}), 401

    package_id = data.get("package_id")
    amount = data.get("amount")
    quantity = data.get("quantity")

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
        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "")
        data = get_users_paginated(page=page, search=search)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": "Data retrieval failed"}), 500

@admin.route("/user/<int:user_id>")
@login_required
def admin_user_profile(user_id):
    from app.services.user_service import get_user_profile
    user = get_user_profile(user_id)
    return render_template("admin/user_profile.html", user=user)

@admin.route("/admin/system-health")
@login_required
def system_health():
    stats = get_system_health()
    return render_template("admin/system_health.html", stats=stats)

@admin.route("/admin/wallet-adjust", methods=["POST"])
@login_required
def wallet_adjust():
    user_id = request.form["user_id"]
    amount = request.form["amount"]
    remark = request.form["remark"]
    admin_wallet_adjust(user_id, amount, remark)
    return redirect("/admin/users")


# ==========================================
# 🛡️ SECURITY MIDDLEWARE
# ==========================================

def is_admin():
    """Helper function to instantly block non-admin users."""
    return current_user.is_authenticated and getattr(current_user, 'role_id', None) == 1


# ==========================================
# 🆔 ENTERPRISE KYC ROUTES
# ==========================================

@admin.route('/kyc/pending', methods=['GET'])
@login_required
def fetch_pending_kyc():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    try:
        return jsonify({"status": "success", "data": get_pending_kyc()}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin.route('/kyc/approve/<int:kyc_id>', methods=['POST'])
@login_required
def process_kyc_approval(kyc_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    try:
        result = approve_kyc(kyc_id, current_user.id)
        return jsonify(result), 200 if result['status'] == 'success' else 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin.route('/kyc/reject/<int:kyc_id>', methods=['POST'])
@login_required
def process_kyc_rejection(kyc_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    data = request.get_json()
    if not data or not data.get('reason'):
        return jsonify({"status": "error", "message": "A rejection reason must be provided."}), 400
    try:
        result = reject_kyc(kyc_id, current_user.id, data.get('reason'))
        return jsonify(result), 200 if result['status'] == 'success' else 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 💰 ENTERPRISE PAYOUT APPROVAL ROUTES
# ==========================================

@admin.route('/payouts/pending', methods=['GET'])
@login_required
def fetch_pending_payouts():
    """Fetches all pending withdrawal requests for admin review."""
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    try:
        return jsonify({"status": "success", "data": get_pending_withdrawals()}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "System Error: Unable to fetch payouts."}), 500

@admin.route('/payouts/approve/<int:request_id>', methods=['POST'])
@login_required
def process_payout_approval(request_id):
    """Approves a withdrawal (Money leaves company)."""
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    try:
        result = approve_withdrawal(request_id, current_user.id)
        return jsonify(result), 200 if result['status'] == 'success' else 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin.route('/payouts/reject/<int:request_id>', methods=['POST'])
@login_required
def process_payout_rejection(request_id):
    """Rejects a withdrawal and AUTO-REFUNDS the user's wallet safely."""
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    
    data = request.get_json()
    reason = data.get('reason', 'Violation of terms or invalid bank details.')
    
    try:
        result = reject_withdrawal(request_id, current_user.id, reason)
        return jsonify(result), 200 if result['status'] == 'success' else 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 📦 DYNAMIC PACKAGE CREATOR ROUTES
# ==========================================

@admin.route('/packages', methods=['GET'])
@login_required
def fetch_packages():
    """Gets all active packages (Combo Plans)."""
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    try:
        return jsonify({"status": "success", "data": get_all_active_packages()}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin.route('/packages/create', methods=['POST'])
@login_required
def create_new_package():
    """
    Creates a new Combo Plan with dynamic commission math.
    Expected JSON: {"name": "Combo A", "price": 100, "direct_commission": 10, "level_commissions": {"1": 0.05, "2": 0.03}}
    """
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    
    data = request.get_json()
    required_fields = ['name', 'price', 'direct_commission']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required package details."}), 400

    try:
        pkg_id = create_package(
            name=data['name'],
            price=data['price'],
            direct_commission=data['direct_commission'],
            level_commissions_dict=data.get('level_commissions', {})
        )
        return jsonify({"status": "success", "message": "Package created successfully.", "package_id": pkg_id}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin.route('/packages/<int:package_id>/deactivate', methods=['POST'])
@login_required
def retire_package(package_id):
    """Safely retires a package without deleting historical commission data."""
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized."}), 403
    try:
        deactivate_package(package_id)
        return jsonify({"status": "success", "message": "Package safely deactivated."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
