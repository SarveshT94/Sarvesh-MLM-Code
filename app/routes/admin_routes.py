from flask import Blueprint, render_template, request, jsonify, session, redirect, flash
from flask_login import login_required, current_user
from app.db import get_cursor

from app.services.payout_service import get_payout_report

# NOTE: user list / team-drill-down / activate / deactivate routes are
# NOT defined here. The live, canonical versions of /admin/users,
# /admin/user/team/<id>, /admin/user/activate/<id>, and
# /admin/user/deactivate/<id> live in app/routes/main.py, which is what
# your navigation and templates actually point to. Keeping only one
# implementation avoids the confusion that happened when this file had
# a second, conflicting copy under /api/admin/....

from app.services.epin_service import generate_epins
from app.services.admin_system_service import get_system_health
from app.services.admin_wallet_service import (
    admin_wallet_adjust, get_pending_withdrawals,
    approve_withdrawal, reject_withdrawal
)
from app.services.kyc_service import get_pending_kyc, approve_kyc, reject_kyc
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

# --- EXISTING ROUTES ---
@admin.route("/generate-epins", methods=["POST"])
@login_required
def generate_epins_api():
    data = request.get_json()
    if not data: return jsonify({"error": "Missing request body"}), 400
    admin_id  = session.get("user_id")
    if not admin_id: return jsonify({"error": "Unauthorized"}), 401
    package_id = data.get("package_id")
    amount     = data.get("amount")
    quantity   = data.get("quantity")
    if not all([package_id, amount, quantity]): return jsonify({"error": "Missing required fields"}), 400
    try:
        result = generate_epins(admin_id=admin_id, package_id=package_id, amount=amount, quantity=quantity)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin.route("/payout-report", methods=["GET"])
@login_required
def payout_report():
    try: return jsonify(get_payout_report()), 200
    except Exception as e: return jsonify({"error": "Failed to fetch report"}), 500


@admin.route("/admin/system-health")
@login_required
def system_health():
    return render_template("admin/system_health.html", stats=get_system_health())

@admin.route("/admin/wallet-adjust", methods=["POST"])
@login_required
def wallet_adjust():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    user_id, amount, action = request.form.get("user_id"), request.form.get("amount"), request.form.get("action", "credit")
    remark, admin_id = request.form.get("remark", ""), session.get("user_id")
    try:
        result = admin_wallet_adjust(user_id, float(amount), action, admin_id, remark)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@admin.route('/kyc/pending', methods=['GET'])
@login_required
def fetch_pending_kyc():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try: return jsonify({"status": "success", "data": get_pending_kyc()}), 200
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@admin.route('/kyc/approve/<int:kyc_id>', methods=['POST'])
@login_required
def process_kyc_approval(kyc_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    return jsonify(approve_kyc(kyc_id, current_user.id))

@admin.route('/kyc/reject/<int:kyc_id>', methods=['POST'])
@login_required
def process_kyc_rejection(kyc_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    data = request.get_json()
    return jsonify(reject_kyc(kyc_id, current_user.id, data.get('reason')))

@admin.route('/admin/withdraws', methods=['GET'])
@login_required
def manage_withdrawals():
    if not is_admin(): return redirect("/")
    return render_template("admin/withdraw_requests.html", requests=get_pending_withdrawals())

@admin.route('/payouts/approve/<int:request_id>', methods=['POST', 'GET'])
@login_required
def process_payout_approval(request_id):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    approve_withdrawal(request_id, current_user.id)
    return redirect("/admin/withdraws")

@admin.route('/payouts/reject/<int:request_id>', methods=['POST'])
@login_required
def process_payout_rejection(request_id):
    try:
        if not is_admin():
            return jsonify({
                "status": "error",
                "message": "Unauthorized"
            }), 403

        data = request.get_json(silent=True) or {}
        remark = data.get("remark", "Rejected by admin")

        from app.services.withdraw_service import reject_withdraw

        reject_withdraw(
            request_id=request_id,
            remark=remark,
            admin_id=current_user.id
        )

        return jsonify({
            "status": "success",
            "message": "Withdraw request rejected successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@admin.route('/packages', methods=['GET'])
@login_required
def fetch_packages():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    return jsonify({"status": "success", "data": get_all_active_packages()}), 200

# --- NEW RANK MANAGEMENT API ROUTES ---
@admin.route('/ranks', methods=['GET'])
@login_required
def get_rank_rules():
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM rank_rules ORDER BY level ASC")
            rules = cur.fetchall()
            safe_rules = []
            for row in rules:
                rule_dict = dict(row)
                if rule_dict.get('req_business_vol') is not None: rule_dict['req_business_vol'] = float(rule_dict['req_business_vol'])
                if rule_dict.get('bonus_percentage') is not None: rule_dict['bonus_percentage'] = float(rule_dict['bonus_percentage'])
                safe_rules.append(rule_dict)
        return jsonify({"status": "success", "data": safe_rules})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@admin.route('/ranks/<int:level>', methods=['PUT'])
@login_required
def update_rank_rule(level):
    if not is_admin(): return jsonify({"status": "error", "message": "Unauthorized"}), 403
    data = request.json
    try:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE rank_rules 
                SET rank_name = %s, req_team_size = %s, req_business_vol = %s, bonus_percentage = %s
                WHERE level = %s
            """, (data.get('rank_name'), data.get('req_team_size'), data.get('req_business_vol'), data.get('bonus_percentage'), level))
        return jsonify({"status": "success", "message": "Updated successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# ==========================================
# COMPANY SETTINGS / BANK DETAILS
# ==========================================

@admin.route('/settings', methods=['GET', 'POST'])
@login_required
def company_settings():
    """Handles viewing and updating Company Profile and Bank Details."""
    if not is_admin(): 
        return redirect("/")
    
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        gst_number = request.form.get('gst_number')
        support_email = request.form.get('support_email')
        support_phone = request.form.get('support_phone')
        head_office = request.form.get('head_office_address')
        branch_address = request.form.get('branch_address')
        logo_url = request.form.get('existing_logo_url')
        bank_name = request.form.get('bank_name')
        acc_name = request.form.get('account_holder_name')
        acc_number = request.form.get('account_number')
        ifsc = request.form.get('ifsc_code')
        upi = request.form.get('upi_id')

        try:
            with get_cursor() as cur:
                cur.execute("""
                    UPDATE company_settings 
                    SET company_name = %s, gst_number = %s, logo_url = %s, 
                        support_email = %s, support_phone = %s, head_office_address = %s, branch_address = %s,
                        bank_name = %s, account_holder_name = %s, account_number = %s, ifsc_code = %s, upi_id = %s
                    WHERE id = 1
                """, (company_name, gst_number, logo_url, support_email, support_phone, head_office, branch_address,
                      bank_name, acc_name, acc_number, ifsc, upi))
            
            flash("Company Profile and Bank details updated successfully!", "success")
        except Exception as e:
            logger.error(f"Error updating company settings: {str(e)}")
            flash("Failed to update details.", "error")
            
        return redirect("/admin/settings")
        
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM company_settings WHERE id = 1")
            settings = cur.fetchone()
    except Exception as e:
        settings = None
        
    return render_template("admin/settings.html", settings=settings)
