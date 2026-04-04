from flask import Blueprint, render_template, request, redirect, jsonify, flash
from flask_login import login_required, current_user
from flask import redirect, url_for

# ✅ THE FIX: We now import the secure Enterprise Connection Pool
from app.db import get_cursor

from app.services.report_service import get_financial_report
from app.services.commission_log_service import get_commission_logs
from app.services.package_service import purchase_package
from app.services.admin_user_service import activate_user, deactivate_user

# Services
from app.services.admin_dashboard_service import get_dashboard_stats
from app.services.wallet_service import get_wallet_balance, get_wallet_history
from app.services.team_service import (
    get_level_1_team,
    get_total_team_count,
    get_genealogy_tree
)

from app.services.admin_user_service import (
    get_all_users,
    activate_user,
    deactivate_user,
    search_users,
    get_users_paginated
)

from app.services.withdraw_service import (
    get_withdraw_requests,
    approve_withdraw,
    reject_withdraw
)

from app.services.kyc_service import (
    submit_kyc,
    get_pending_kyc,
    approve_kyc,
    reject_kyc
)

main = Blueprint("main", __name__)


# ------------------------------------------------
# Home Route
# ------------------------------------------------
@main.route("/")
def home():
    return jsonify({
        "message": "RK Trendz MLM Backend Running 🚀"
    })


# ------------------------------------------------
# Database Test (✅ UPGRADED TO CONNECTION POOL)
# ------------------------------------------------
@main.route("/test-db")
def test_db():
    try:
        # We use 'with' so the pool automatically borrows and returns the connection
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


# ------------------------------------------------
# Wallet Balance
# ------------------------------------------------
@main.route("/wallet/<int:user_id>")
def wallet_balance(user_id):
    balance = get_wallet_balance(user_id)
    return jsonify({
        "user_id": user_id,
        "wallet_balance": float(balance)
    })


# ------------------------------------------------
# Wallet History
# ------------------------------------------------
@main.route("/wallet/<int:user_id>/history")
def wallet_history(user_id):
    history = get_wallet_history(user_id)
    return jsonify({
        "user_id": user_id,
        "transactions": history
    })


# ------------------------------------------------
# Team Information
# ------------------------------------------------
@main.route("/team/<int:user_id>")
def team(user_id):
    level1 = get_level_1_team(user_id)
    total = get_total_team_count(user_id)
    return jsonify({
        "user_id": user_id,
        "direct_team": level1,
        "total_team": total
    })


# ------------------------------------------------
# Genealogy Tree
# ------------------------------------------------
@main.route("/genealogy/<int:user_id>")
def genealogy(user_id):
    tree = get_genealogy_tree(user_id)
    return jsonify({
        "user_id": user_id,
        "team_tree": tree
    })


# ------------------------------------------------
# Admin Dashboard API
# ------------------------------------------------
@main.route("/admin/dashboard")
def admin_dashboard():
    stats = get_dashboard_stats()
    return jsonify({
        "success": True,
        "data": stats
    })


# ------------------------------------------------
# Admin Dashboard UI
# ------------------------------------------------
@main.route("/admin/panel")
def admin_panel():
    stats = get_dashboard_stats()
    return render_template(
        "admin/dashboard.html",
        stats=stats
    )


# ------------------------------------------------
# Admin Users (Pagination)
# ------------------------------------------------
@main.route("/admin/users")
def admin_users():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "")

    data = get_users_paginated(page, search)

    return render_template(
        "admin/users.html",
        users=data["users"],
        total=data["total"],
        page=data["page"],
        pages=data["pages"],
        search=search
    )

# ------------------------------------------------
# Admin User Search
# ------------------------------------------------
@main.route("/admin/users/search")
def admin_users_search():
    search = request.args.get("q", "")
    page = int(request.args.get("page", 1))

    data = get_users_paginated(page, search)

    return render_template(
        "admin/users.html",
        users=data["users"],
        total=data["total"],
        page=data["page"],
        pages=data["pages"],
        search=search
    )


# ------------------------------------------------
# Activate User
# ------------------------------------------------
@main.route("/admin/user/activate/<int:user_id>", methods=['GET', 'POST'])
def admin_activate_user(user_id):
    activate_user(user_id)
    flash("User activated successfully", "success")
    return redirect("/admin/users")

# ------------------------------------------------
# Deactivate user
# ------------------------------------------------
@main.route("/admin/user/deactivate/<int:user_id>", methods=['GET', 'POST'])
def admin_deactivate_user(user_id):
    deactivate_user(user_id)
    flash("User deactivated successfully", "success")
    return redirect("/admin/users")

# ------------------------------------------------
# Admin Withdraw Requests
# ------------------------------------------------
@main.route("/admin/withdraws")
def admin_withdraws():
    requests = get_withdraw_requests()
    return render_template(
        "admin/withdraw_requests.html",
        requests=requests
    )


# ------------------------------------------------
# Approve Withdraw
# ------------------------------------------------
@main.route("/admin/withdraw/approve/<int:request_id>")
def admin_approve_withdraw(request_id):
    approve_withdraw(request_id)
    return redirect("/admin/withdraws")


# ------------------------------------------------
# Reject Withdraw
# ------------------------------------------------
@main.route("/admin/withdraw/reject/<int:request_id>")
def admin_reject_withdraw(request_id):
    reject_withdraw(request_id, "Rejected by admin")
    return redirect("/admin/withdraws")


# ------------------------------------------------
# MLM Financial Report
# ------------------------------------------------
@main.route("/admin/reports/financial")
def financial_report():
    report = get_financial_report()
    return jsonify({
        "success": True,
        "report": report
    })


@main.route("/admin/reports")
def admin_financial_report():
    report = get_financial_report()
    return render_template(
        "admin/financial_report.html",
        report=report
    )


# ------------------------------------------------
# Commission Logs (Admin)
# ------------------------------------------------
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


# ------------------------------------------------
# Submit KYC
# ------------------------------------------------
@main.route("/user/kyc-submit", methods=["POST"])
def user_submit_kyc():
    data = request.json
    submit_kyc(
        data["user_id"],
        data["document_type"],
        data["document_number"],
        data["document_image"],
        data["selfie_image"]
    )
    return jsonify({
        "success": True,
        "message": "KYC submitted"
    })


# ------------------------------------------------
# Admin KYC Requests
# ------------------------------------------------
@main.route("/admin/kyc")
def admin_kyc():
    kyc = get_pending_kyc()
    return render_template(
        "admin/kyc_list.html",
        kyc=kyc
    )


@main.route("/admin/approve-kyc/<int:kyc_id>", methods=["POST"])
@login_required
def admin_approve_kyc(kyc_id):
    # Security Check: Ensure only Admins can do this
    if getattr(current_user, 'role_id', None) != 1: 
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    approve_kyc(kyc_id)

    return jsonify({
        "success": True,
        "message": "KYC approved"
    })


@main.route("/admin/reject-kyc/<int:kyc_id>", methods=["POST"])
@login_required
def admin_reject_kyc(kyc_id):
    # Security Check
    if getattr(current_user, 'role_id', None) != 1:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    note = request.args.get("note", "")
    reject_kyc(kyc_id, note)

    return jsonify({
        "success": True,
        "message": "KYC rejected"
    })


@main.route("/purchase-package", methods=["POST"])
def purchase_package_api():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        package_id = data.get("package_id")

        if not user_id or not package_id:
            return jsonify({
                "success": False,
                "message": "user_id and package_id required"
            }), 400

        result = purchase_package(
            user_id=user_id,
            package_id=package_id
        )

        if not result["success"]:
            return jsonify(result), 400

        return jsonify({
            "success": True,
            "message": "Package purchased successfully",
            "purchase_id": result["purchase_id"],
            "amount": result["amount"]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
