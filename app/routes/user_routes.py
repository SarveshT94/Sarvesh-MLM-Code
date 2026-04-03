from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

# --- Enterprise Service Imports ---
from app.services.wallet_service import get_wallet_balance, request_withdrawal
from app.services.kyc_service import submit_kyc
from app.services.income_service import get_income_summary
from app.services.rank_service import get_user_rank
from app.services.epin_service import redeem_epin  # Added missing import

# Create the User Blueprint (Matches __init__.py)
user_bp = Blueprint('user', __name__)

# ==========================================
# 💰 USER WALLET ROUTES
# ==========================================

@user_bp.route('/wallet/balance', methods=['GET'])
@login_required
def fetch_my_balance():
    """Retrieves the exact, dynamically calculated wallet balance."""
    try:
        balance = get_wallet_balance(current_user.id)
        return jsonify({
            "status": "success",
            "message": "Wallet balance retrieved successfully.",
            "data": {"balance": str(balance)} 
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "System Error: Unable to calculate balance."}), 500

@user_bp.route('/wallet/withdraw', methods=['POST'])
@login_required
def process_withdrawal_request():
    """Submits a safe withdrawal request using double-entry locking."""
    data = request.get_json()
    amount = data.get('amount')

    if not amount:
        return jsonify({"status": "error", "message": "Withdrawal amount is required."}), 400

    try:
        result = request_withdrawal(current_user.id, amount)
        status_code = 200 if result.get('status') == 'success' else 400
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# 🆔 USER KYC ROUTES
# ==========================================

@user_bp.route('/kyc/submit', methods=['POST'])
@login_required
def upload_kyc_documents():
    """Submits Aadhaar/PAN details for Admin review."""
    data = request.get_json()
    doc_type = data.get('document_type')
    doc_number = data.get('document_number')

    if not doc_type or not doc_number:
        return jsonify({"status": "error", "message": "Document type and number are required."}), 400

    try:
        result = submit_kyc(current_user.id, doc_type, doc_number)
        status_code = 200 if result.get('status') == 'success' else 400
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# 🎟️ E-PIN & PACKAGE ACTIVATION
# ==========================================

@user_bp.route("/redeem-epin", methods=["POST"])
@login_required
def redeem_epin_api():
    """Allows a user to activate a package using a pre-purchased E-Pin."""
    data = request.get_json()
    pin_code = data.get("pin_code")

    if not pin_code:
        return jsonify({"status": "error", "message": "PIN code is required."}), 400

    try:
        result = redeem_epin(current_user.id, pin_code)
        
        # Assuming your redeem_epin service returns a dict with 'success' or 'status'
        # We wrap it to ensure standard enterprise JSON formatting
        if isinstance(result, dict) and (result.get('status') == 'success' or result.get('success') is True):
             return jsonify({"status": "success", "message": "E-Pin redeemed successfully.", "data": result}), 200
        else:
             return jsonify({"status": "error", "message": result.get('message', 'Invalid or used E-Pin.')}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# 📊 INCOME & RANK DASHBOARD
# ==========================================

@user_bp.route("/dashboard-income", methods=["GET"])
@login_required
def dashboard_income():
    """Fetches a breakdown of the user's earnings."""
    try:
        result = get_income_summary(current_user.id)
        return jsonify({
            "status": "success",
            "message": "Income summary retrieved.",
            "data": result
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to fetch income summary."}), 500

@user_bp.route("/my-rank", methods=["GET"])
@login_required
def my_rank():
    """Fetches the user's current MLM rank and progression."""
    try:
        rank = get_user_rank(current_user.id)
        return jsonify({
            "status": "success",
            "message": "Rank retrieved successfully.",
            "data": rank
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to fetch rank info."}), 500
