from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.kyc_service import submit_kyc
from app.services.income_service import get_income_summary
from app.services.rank_service import get_user_rank
from app.services.epin_service import redeem_epin
from app.services.withdraw_service import create_withdraw_request
from app.services.wallet_service import get_wallet_balance, get_wallet_history
from app.services.sponsor_service import get_sponsor_chain

from app.services.team_service import get_total_team_count, get_level_1_team, get_genealogy_tree

import logging

logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__)

# -----------------------------------
# 1. NETWORK & TEAM ROUTES
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
    """
    Folds the flat downline list (root + all descendants, each tagged
    with `level`, from get_genealogy_tree) into a nested JSON tree for
    the React chart.
    """
    try:
        uid_str = str(current_user.id)

        flat_list = get_genealogy_tree(current_user.id)

        if not flat_list:
            return jsonify({"team_tree": {}}), 200

        # Step 1: map every node and give it an empty children array
        nodes = {}
        for item in flat_list:
            node = dict(item)
            node_id = str(node.get("id"))
            node["id"] = node_id
            node["user_id"] = node_id
            node["children"] = []
            nodes[node_id] = node

        # get_genealogy_tree always includes the root user's own row
        # (level 0), so this is a safety net rather than the normal
        # path -- but we keep it so a data anomaly degrades gracefully
        # instead of returning an empty tree.
        if uid_str not in nodes:
            logger.error(f"Genealogy root missing from flat list | user={uid_str}")
            nodes[uid_str] = {"id": uid_str, "user_id": uid_str, "children": []}

        # Step 2: attach each node to its parent's children array.
        # FIX: `str(node.get("sponsor_id"))` used to turn a real None
        # into the *string* "None", which is truthy -- so the
        # `if parent_id` guard never caught a genuinely missing
        # sponsor, it just silently failed the `in nodes` check and
        # the node was dropped from the tree with no trace. Now we
        # check for None explicitly and log orphans instead of
        # discarding them silently.
        for node_id, node in nodes.items():
            if node_id == uid_str:
                continue
            raw_parent = node.get("sponsor_id")
            parent_id = str(raw_parent) if raw_parent is not None else None
            if parent_id is None:
                continue
            if parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                logger.error(
                    f"Orphan node in genealogy tree | node={node_id} "
                    f"missing_parent={parent_id} root={uid_str}"
                )

        root_node = nodes[uid_str]
        return jsonify({"team_tree": root_node}), 200

    except Exception as e:
        logger.error(f"Genealogy API error: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to map tree"}), 500


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
    data = request.get_json(silent=True) or {}
    raw_amount = data.get('amount')

    if raw_amount is None or raw_amount == '':
        return jsonify({"status": "error", "message": "Withdrawal amount is required"}), 400

    # FIX: previously only checked truthiness (`if not amount`), which
    # rejects 0/None/"" but does NOT reject non-numeric strings,
    # negative numbers, or absurdly large values -- all of which would
    # have been passed straight through to create_withdraw_request.
    try:
        amount = float(raw_amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid withdrawal amount"}), 400

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
    data = request.get_json(silent=True) or {}
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
        logger.error(f"KYC submit error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@user_bp.route('/redeem-epin', methods=['POST'])
@login_required
def redeem_epin_api():
    data = request.get_json(silent=True) or {}
    pin_code = data.get('pin_code')
    if not pin_code:
        return jsonify({"status": "error", "message": "PIN code is required"}), 400
    try:
        result = redeem_epin(current_user.id, pin_code)
        if isinstance(result, dict) and (result.get('status') == 'success' or result.get('success')):
            return jsonify({"status": "success", "message": "E-Pin redeemed.", "data": result}), 200
        return jsonify({"status": "error", "message": result.get('message', 'Invalid E-Pin')}), 400
    except Exception as e:
        logger.error(f"Redeem epin error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@user_bp.route('/dashboard-income', methods=['GET'])
@login_required
def dashboard_income():
    try:
        result = get_income_summary(current_user.id)
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        # FIX: previously no logger.error call here, unlike every
        # other route -- failures were invisible in the logs.
        logger.error(f"Dashboard income error: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to fetch income summary"}), 500


@user_bp.route('/my-rank', methods=['GET'])
@login_required
def my_rank():
    try:
        rank = get_user_rank(current_user.id)
        return jsonify({"status": "success", "data": rank}), 200
    except Exception as e:
        # FIX: same missing-logging issue as dashboard_income.
        logger.error(f"My rank error: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to fetch rank"}), 500
