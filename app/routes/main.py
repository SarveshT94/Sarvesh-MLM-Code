from flask import Blueprint, render_template, request, redirect, jsonify, flash, url_for
from flask_login import login_required, current_user

from app.db import get_cursor

# Services
from app.services.report_service import get_financial_report
from app.services.commission_log_service import get_commission_logs
from app.services.package_service import purchase_package

from app.services.admin_dashboard_service import get_dashboard_stats
from app.services.wallet_service import get_wallet_balance, get_wallet_history

from app.services.team_service import (
    get_level_1_team,
    get_total_team_count,
    get_genealogy_tree
)

from app.services.admin_user_service import (
    activate_user,
    deactivate_user,
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


# =========================================================
# 🔥 HOME = DASHBOARD (SAFE VERSION - NO CRASH)
# =========================================================
@main.route("/")
def home():
    return "<h1 style='color:green;'>NOW IT WORKS ✅</h1>"


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
# ADMIN DASHBOARD
# =========================================================
@main.route("/admin/dashboard")
def admin_dashboard():
    try:
        stats = get_dashboard_stats()
    except:
        stats = {}

    return jsonify({
        "success": True,
        "data": stats
    })


@main.route("/admin/panel")
def admin_panel():
    try:
        stats = get_dashboard_stats()
    except:
        stats = {}

    return render_template("admin/dashboard.html", stats=stats)


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
# KYC
# =========================================================
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


@main.route("/admin/kyc")
def admin_kyc():
    kyc = get_pending_kyc()

    return render_template(
        "admin/kyc_list.html",
        kyc=kyc
    )
