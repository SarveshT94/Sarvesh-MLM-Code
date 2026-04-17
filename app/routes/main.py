from flask import Blueprint, render_template, request, redirect, jsonify, flash, url_for
from flask_login import login_required, current_user

from app.db import get_cursor

# Services
from app.services.report_service import get_financial_report
from app.services.commission_log_service import get_commission_logs
from app.services.package_service import purchase_package
from app.services.admin_dashboard_service import get_dashboard_stats
from app.services.wallet_service import get_wallet_balance, get_wallet_history
from app.services.team_service import get_level_1_team, get_total_team_count, get_genealogy_tree
from app.services.admin_user_service import activate_user, deactivate_user, get_users_paginated
from app.services.withdraw_service import get_withdraw_requests, approve_withdraw, reject_withdraw
from app.services.kyc_service import submit_kyc, get_pending_kyc, approve_kyc, reject_kyc

main = Blueprint("main", __name__)


# =========================================================
# 🔥 HOME & DASHBOARD 
# =========================================================
@main.route("/")
@main.route("/admin/panel")
def home():
    try:
        stats = get_dashboard_stats()
    except Exception as e:
        stats = {}

    return render_template("admin/dashboard.html", stats=stats)


# =========================================================
# 🔥 HEALTH CHECK API
# =========================================================
@main.route("/api/health")
def health_check():
    return jsonify({
        "status": "success",
        "message": "RK Trendz MLM Backend Running 🚀"
    })


# =========================================================
# DB TEST
# =========================================================
@main.route("/test-db")
def test_db():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT NOW() AS server_time")
            result = cur.fetchone()

        return jsonify({
            "status": "success",
            "server_time": result["server_time"]
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


# =========================================================
# WALLET
# =========================================================
@main.route("/wallet/<int:user_id>")
def wallet_balance(user_id):
    result = get_wallet_balance(user_id)
    return jsonify({
        "user_id": user_id,
        "wallet_balance": result.get("balance", 0)
    })

@main.route("/wallet/<int:user_id>/history")
def wallet_history(user_id):
    result = get_wallet_history(user_id)
    return jsonify({
        "user_id": user_id,
        "transactions": result.get("data", [])
    })


# =========================================================
# TEAM
# =========================================================
@main.route("/team/<int:user_id>")
def team(user_id):
    return jsonify({
        "user_id": user_id,
        "direct_team": get_level_1_team(user_id),
        "total_team": get_total_team_count(user_id)
    })

@main.route("/genealogy/<int:user_id>")
def genealogy(user_id):
    return jsonify({
        "user_id": user_id,
        "team_tree": get_genealogy_tree(user_id)
    })


# =========================================================
# 🔥 ADMIN TEAM VIEW
# =========================================================
@main.route("/admin/user/team/<int:user_id>")
def admin_user_team(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id, full_name, created_at FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
    except Exception as e:
        user = None

    if not user:
        flash("User not found.", "danger")
        return redirect("/admin/users")

    raw_tree = get_genealogy_tree(user_id)
    team_tree = {}
    
    if isinstance(raw_tree, list):
        for row in raw_tree:
            # Cast the RealDictRow to a standard mutable Python dict
            member = dict(row) 
            lvl = member.get('level', 1)
            
            # Smart fallback: look for full_name, then name, then username, then default
            member_name = member.get('full_name') or member.get('name') or member.get('username') or f"User #{member.get('id', '?')}"
            member['full_name'] = member_name
            
            if lvl not in team_tree:
                team_tree[lvl] = []
            team_tree[lvl].append(member)
            
    elif isinstance(raw_tree, dict):
        team_tree = raw_tree

    return render_template("admin/user_team.html", user=user, team_tree=team_tree)

# =========================================================
# ADMIN API DASHBOARD
# =========================================================
@main.route("/admin/dashboard")
def admin_dashboard():
    try:
        stats = get_dashboard_stats()
    except Exception as e:
        stats = {}

    return jsonify({
        "success": True,
        "data": stats
    })


# =========================================================
# USERS
# =========================================================
@main.route("/admin/users")
def admin_users():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "")

    data = get_users_paginated(page, search)

    return render_template(
        "admin/users.html",
        users=data.get("users", []),
        total=data.get("total", 0),
        page=data.get("page", 1),
        pages=data.get("pages", 1),
        search=search
    )

@main.route("/admin/user/activate/<int:user_id>", methods=["POST"])
def admin_activate_user(user_id):
    activate_user(user_id)
    flash("User activated successfully", "success")
    return redirect("/admin/users")

@main.route("/admin/user/deactivate/<int:user_id>", methods=["POST"])
def admin_deactivate_user(user_id):
    deactivate_user(user_id)
    flash("User deactivated successfully", "success")
    return redirect("/admin/users")


# =========================================================
# WITHDRAW
# =========================================================
@main.route("/admin/withdraws")
def admin_withdraws():
    requests = get_withdraw_requests()
    return render_template(
        "admin/withdraw_requests.html",
        requests=requests
    )

@main.route("/admin/withdraw/approve/<int:request_id>")
def admin_approve_withdraw(request_id):
    approve_withdraw(request_id)
    return redirect("/admin/withdraws")

@main.route("/admin/withdraw/reject/<int:request_id>")
def admin_reject_withdraw(request_id):
    reject_withdraw(request_id, "Rejected by admin")
    return redirect("/admin/withdraws")


# =========================================================
# REPORTS
# =========================================================
@main.route("/admin/reports")
def admin_financial_report():
    report = get_financial_report()
    return render_template(
        "admin/financial_report.html",
        report=report
    )

@main.route("/admin/commission-logs")
def admin_commission_logs():
    page = request.args.get("page", 1, type=int)
    limit = 50
    offset = (page - 1) * limit
    logs = get_commission_logs(limit, offset)

    return render_template(
        "admin/commission_logs.html",
        logs=logs,
        page=page
    )


# =========================================================
# KYC (ENTERPRISE API)
# =========================================================
@main.route('/api/user/kyc', methods=['GET', 'POST'])
@login_required
def api_user_kyc():
    """Enterprise API endpoint for Customer KYC."""
    
    # [GET] Send current status to the frontend
    if request.method == 'GET':
        try:
            with get_cursor() as cur:
                cur.execute("""
                    SELECT kyc_status, kyc_rejection_reason, pan_number, aadhar_number, 
                           bank_name, bank_account_no, bank_ifsc 
                    FROM users WHERE id = %s
                """, (current_user.id,))
                user_data = cur.fetchone()
                
            return jsonify({"status": "success", "data": user_data}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # [POST] Accept new KYC documents from the frontend
    if request.method == 'POST':
        data = request.get_json()
        
        try:
            with get_cursor() as cur:
                cur.execute("SELECT kyc_status FROM users WHERE id = %s", (current_user.id,))
                status_row = cur.fetchone()
                current_status = status_row['kyc_status'] if status_row else None
                
            if current_status in ['approved', 'pending']:
                return jsonify({"status": "error", "message": "KYC is currently locked for review or already approved."}), 400

            result = submit_kyc(
                user_id=current_user.id,
                pan_number=data.get('pan_number'),
                aadhar_number=data.get('aadhar_number'),
                bank_name=data.get('bank_name'),
                bank_account_no=data.get('bank_account_no'),
                bank_ifsc=data.get('bank_ifsc')
            )
            return jsonify(result), 200
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@main.route("/admin/kyc")
def admin_kyc():
    """Renders the Admin KYC queue dashboard."""
    kyc = get_pending_kyc()
    return render_template(
        "admin/kyc_list.html",
        kyc=kyc
    )
