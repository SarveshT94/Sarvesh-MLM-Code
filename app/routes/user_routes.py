from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.kyc_service import submit_kyc
from app.services.income_service import get_income_summary
from app.services.rank_service import get_user_rank
from app.services.epin_service import redeem_epin
from app.services.withdraw_service import create_withdraw_request
from app.services.wallet_service import get_wallet_balance, get_wallet_history

# 🔥 NEW IMPORTS FOR NETWORK & TEAM
from app.services.team_service import get_total_team_count, get_level_1_team
from app.services.admin.tree_service import get_user_tree
from app.services.sponsor_service import get_sponsor_chain

import logging

logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__)


# -----------------------------------
# 1. NETWORK & TEAM ROUTES (THE 404 FIX)
# -----------------------------------
@user_bp.route('/team/me', methods=['GET'])
@login_required
def get_team_me():
    try:
        uid = current_user.id
        return jsonify({
            "total_team": get_total_team_count(uid),
            "direct_team": get_level_1_team(uid)
        }), 200
    except Exception as e:
        logger.error(f"Team API error: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to fetch team"}), 500

@user_bp.route('/genealogy/me', methods=['GET'])
@login_required
def get_genealogy_me():
    try:
        uid = current_user.id
        tree = get_user_tree(uid)
        return jsonify({"team_tree": tree}), 200
    except Exception as e:
        logger.error(f"Genealogy API error: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to fetch tree"}), 500

@user_bp.route('/team/upline', methods=['GET'])
@login_required
def get_upline_me():
    try:
        uid = current_user.id
        chain = get_sponsor_chain(uid)
        return jsonify(chain), 200
    except Exception as e:
        logger.error(f"Upline API error: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to fetch upline"}), 500


# -----------------------------------
# 2. WALLET ROUTES
# -----------------------------------
@user_bp.route('/wallet/balance', methods=['GET'])
@login_required
def fetch_my_balance():
    try:
        from app.db import get_cursor
        with get_cursor() as cur:
            result = get_wallet_balance(cur, current_user.id)
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        logger.error(f"Balance error: {str(e)}")
        return jsonify({"status": "error", "message": "Unable to fetch balance"}), 500


@user_bp.route('/wallet/history', methods=['GET'])
@login_required
def fetch_wallet_history():
    try:
        from app.db import get_cursor
        with get_cursor() as cur:
            result = get_wallet_history(cur, current_user.id)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Wallet history error: {str(e)}")
        return jsonify({"status": "error", "message": "Unable to fetch history"}), 500


@user_bp.route('/wallet/withdraw', methods=['POST'])
@login_required
def process_withdrawal_request():
    data   = request.get_json()
    amount = data.get('amount')

    if not amount:
        return jsonify({"status": "error", "message": "Withdrawal amount is required"}), 400

    try:
        result = create_withdraw_request(
            user_id=current_user.id,
            amount=amount,
            payout_method=data.get('payout_method', 'bank'),
            payout_details=data.get('payout_details', '')
        )
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Withdrawal error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# -----------------------------------
# 3. OTHER USER ROUTES
# -----------------------------------
@user_bp.route('/kyc/submit', methods=['POST'])
@login_required
def upload_kyc_documents():
    data = request.get_json()
    try:
        result = submit_kyc(
            user_id=current_user.id,
            pan_number=data.get('pan_number'),
            aadhar_number=data.get('aadhar_number'),
            bank_name=data.get('bank_name'),
            bank_account_no=data.get('bank_account_no'),
            bank_ifsc=data.get('bank_ifsc')
        )
        return jsonify(result), 200 if result.get('status') == 'success' else 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@user_bp.route('/redeem-epin', methods=['POST'])
@login_required
def redeem_epin_api():
    data     = request.get_json()
    pin_code = data.get('pin_code')
    if not pin_code:
        return jsonify({"status": "error", "message": "PIN code is required"}), 400
    try:
        result = redeem_epin(current_user.id, pin_code)
        if isinstance(result, dict) and (result.get('status') == 'success' or result.get('success')):
            return jsonify({"status": "success", "message": "E-Pin redeemed.", "data": result}), 200
        return jsonify({"status": "error", "message": result.get('message', 'Invalid E-Pin')}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@user_bp.route('/dashboard-income', methods=['GET'])
@login_required
def dashboard_income():
    try:
        result = get_income_summary(current_user.id)
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to fetch income summary"}), 500


@user_bp.route('/my-rank', methods=['GET'])
@login_required
def my_rank():
    try:
        rank = get_user_rank(current_user.id)
        return jsonify({"status": "success", "data": rank}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to fetch rank"}), 500
