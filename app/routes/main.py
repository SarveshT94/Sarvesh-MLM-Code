from flask import Blueprint, render_template, request, redirect, jsonify, flash, url_for
from flask_login import login_required, current_user
import logging

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
from app.services.kyc_service import submit_kyc, get_pending_kyc
from app.services.risk_service import get_risk_dashboard, auto_block_high_risk_users

logger = logging.getLogger(__name__)
main = Blueprint("main", __name__)


# =========================================================
# 🔥 HOME & DASHBOARD 
# =========================================================
@main.route("/")
@main.route("/admin/panel")
def home():
    try:
        auto_block_high_risk_users()
        stats = get_dashboard_stats()
    except Exception as e:
        logger.error(f"Dashboard load error: {str(e)}")
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
        logger.error(f"DB test failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Database connection failed"
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
    except Exception:
        user = None

    if not user:
        flash("User not found.", "danger")
        return redirect("/admin/users")

    raw_tree = get_genealogy_tree(user_id)
    team_tree = {}

    if isinstance(raw_tree, list):
        for row in raw_tree:
            member = dict(row)
            lvl = member.get('level', 1)

            member_name = member.get('full_name') or member.get('name') or member.get('username') or f"User #{member.get('id', '?')}"
            member['full_name'] = member_name

            if lvl not in team_tree:
                team_tree[lvl] = []
            team_tree[lvl].append(member)

    elif isinstance(raw_tree, dict):
        team_tree = raw_tree

    return render_template("admin/user_team.html", user=user, team_tree=team_tree)


# =========================================================
# ADMIN DASHBOARD API
# =========================================================
@main.route("/admin/dashboard")
def admin_dashboard():
    try:
        stats = get_dashboard_stats()
    except Exception:
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


# ----------------------------------
# ADMIN WITHDRAW QUEUE
# ----------------------------------
@main.route("/admin/withdraws")
def admin_withdraws():
    try:
        requests = get_withdraw_requests()
    except Exception as e:
        logger.error(f"Error loading withdraws: {str(e)}")
        requests = []

    return render_template(
        "admin/withdraw_requests.html",
        requests=requests
    )

# ✅ FIXED: Added Try/Except so accidental double clicks don't crash the server
@main.route("/admin/withdraw/approve/<int:request_id>")
def admin_approve_withdraw(request_id):
    try:
        approve_withdraw(request_id)
        flash("Withdrawal approved successfully!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        
    return redirect("/admin/withdraws")


# ✅ FIXED: Added Try/Except so accidental double clicks don't crash the server
@main.route("/admin/withdraw/reject/<int:request_id>", methods=['GET', 'POST'])
def admin_reject_withdraw(request_id):
    reason = "Rejected by admin"
    if request.method == 'POST':
        reason = request.form.get("reason", reason)
        
    try:
        reject_withdraw(request_id, reason)
        flash("Withdrawal rejected and refunded.", "warning")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        
    return redirect("/admin/withdraws")


# =========================================================
# REPORTS
# =========================================================
@main.route("/admin/reports")
def admin_financial_report():
    report = get_financial_report()
    return render_template("admin/financial_report.html", report=report)


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
# KYC API
# =========================================================
@main.route('/api/user/kyc', methods=['GET', 'POST'])
def api_user_kyc():
    if not current_user.is_authenticated:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

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

    if request.method == 'POST':
        data = request.get_json()

        try:
            with get_cursor() as cur:
                cur.execute("SELECT kyc_status FROM users WHERE id = %s", (current_user.id,))
                status_row = cur.fetchone()
                current_status = status_row['kyc_status'] if status_row else None

            if current_status in ['approved', 'pending']:
                return jsonify({"status": "error", "message": "KYC locked"}), 400

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
    kyc = get_pending_kyc()
    return render_template("admin/kyc_list.html", kyc=kyc)


# =========================================================
# 🚨 RISK MONITOR API
# =========================================================
@main.route("/admin/risk-users")
def admin_risk_users():
    try:
        data = get_risk_dashboard()

        return jsonify({
            "status": "success",
            "count": len(data),
            "data": data
        })

    except Exception as e:
        logger.error(f"Risk API error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to fetch risk data"
        }), 500


# =========================================================
# 🚨 RISK MONITOR PAGE
# =========================================================
@main.route("/admin/risk-monitor")
def risk_monitor():
    try:
        # 🔍 Filters from query params
        risk_filter = request.args.get("risk")
        status_filter = request.args.get("status")
        search = request.args.get("q", "").lower()

        risk_data = get_risk_dashboard()

        # =================================================
        # APPLY FILTERS (SAFE)
        # =================================================
        filtered_data = []

        for user in risk_data:

            # Risk filter
            if risk_filter and user["risk_level"] != risk_filter:
                continue

            # Status filter
            if status_filter:
                if status_filter == "active" and not user["is_active"]:
                    continue
                if status_filter == "blocked" and user["is_active"]:
                    continue

            # Search filter
            if search:
                name = (user.get("name") or "").lower()
                email = (user.get("email") or "").lower()

                if search not in name and search not in email:
                    continue

            filtered_data.append(user)

        # Summary (based on filtered data)
        summary = {
            "high": sum(1 for u in filtered_data if u["risk_level"] == "high"),
            "medium": sum(1 for u in filtered_data if u["risk_level"] == "medium"),
            "low": sum(1 for u in filtered_data if u["risk_level"] == "low"),
        }

        return render_template(
            "admin/risk_monitor.html",
            risk_data=filtered_data,
            summary=summary,
            filters={
                "risk": risk_filter,
                "status": status_filter,
                "q": search
            }
        )

    except Exception as e:
        logger.error(f"Risk monitor error: {str(e)}")
        return "Error loading risk panel"


# =========================================================
# API (Future use)
# =========================================================
@main.route("/api/admin/risk-data")
def api_risk_data():
    try:
        return jsonify({
            "status": "success",
            "data": get_risk_dashboard()
        })
    except Exception as e:
        logger.error(f"Risk API error: {str(e)}")
        return jsonify({"status": "error"})


# =========================================================
# 🚨 ADMIN BLOCK USER
# =========================================================
@main.route("/admin/block-user/<int:user_id>", methods=["POST"])
def admin_block_user(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE users
                SET is_active = FALSE
                WHERE id = %s
                AND is_active = TRUE
            """, (user_id,))

        flash("User blocked successfully", "danger")

    except Exception as e:
        logger.error(f"Block user failed: {str(e)}")
        flash("Error blocking user", "danger")

    return redirect(url_for("main.risk_monitor"))


# =========================================================
# 🚨 ADMIN UNBLOCK USER
# =========================================================
@main.route("/admin/unblock-user/<int:user_id>", methods=["POST"])
def admin_unblock_user(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE users
                SET is_active = TRUE
                WHERE id = %s
                AND is_active = FALSE
            """, (user_id,))

        flash("User unblocked successfully", "success")

    except Exception as e:
        logger.error(f"Unblock user failed: {str(e)}")
        flash("Error unblocking user", "danger")

    return redirect(url_for("main.risk_monitor"))


# =========================================================
# 🔐 AUTHENTICATION API (For Next.js)
# =========================================================
@main.route("/api/auth/me", methods=["GET"])
def check_session():
    if current_user.is_authenticated:
        return jsonify({
            "success": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name
            }
        }), 200
    else:
        return jsonify({"success": False, "message": "Unauthorized"}), 401


#______________________________________________________
@main.route("/test/credit/<int:user_id>/<int:amount>")
def test_credit(user_id, amount):
    try:
        from app.services.wallet_service import credit_wallet
        from datetime import datetime

        with get_cursor() as cur:

            # ✅ UNIQUE reference every time
            reference = f"test_credit_{user_id}_{datetime.utcnow().timestamp()}"

            credit_wallet(
                cur,
                user_id,
                amount,
                reference=reference,
                description="Test credit"
            )

        return f"✅ Credited {amount} to user {user_id}"

    except Exception as e:
        return str(e)


@main.route("/test/create-withdraw/<int:user_id>/<int:amount>")
def test_create_withdraw(user_id, amount):
    from app.services.withdraw_service import create_withdraw_request

    result = create_withdraw_request(user_id, amount)
    return jsonify(result)

@main.route("/test/clear-withdraw/<int:user_id>")
def clear_withdraw(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                DELETE FROM withdraw_requests
                WHERE user_id = %s
            """, (user_id,))
        return "✅ Cleared withdraw requests"
    except Exception as e:
        return str(e)


@main.route("/test-route")
def test_route():
    return "Working"
