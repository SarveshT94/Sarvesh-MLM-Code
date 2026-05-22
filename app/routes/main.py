from flask import Blueprint, render_template, request, redirect, jsonify, flash, url_for, session
from flask_login import login_required, current_user, login_user, logout_user
import logging
import os
from werkzeug.utils import secure_filename
from flask import current_app
from functools import wraps

from app.db import get_cursor
from app.services.user_service import authenticate_user
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


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, 'role_id', 2) != 1:
            flash("Unauthorized. Please log in as an Admin.", "danger")
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated_function


# =========================================================
# ADMIN LOGIN / LOGOUT
# =========================================================
@main.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated and getattr(current_user, 'role_id', 2) == 1:
        return redirect("/admin/panel")
    if request.method == "POST":
        identifier = request.form.get("identifier")
        password   = request.form.get("password")
        result     = authenticate_user(identifier, password)
        if result['status'] == 'success':
            user_dict = result['user']
            if user_dict.get('role_id') == 1:
                from app.routes.auth_routes import AuthUser
                login_user(AuthUser(user_dict))
                return redirect("/admin/panel")
            else:
                flash("Access Denied: You do not have Admin privileges.", "danger")
        else:
            flash("Invalid email/ID or password.", "danger")
    return render_template("admin/login.html")


@main.route("/admin/logout")
def admin_logout():
    logout_user()
    session.clear()
    flash("You have been securely logged out.", "success")
    return redirect("/admin/login")


# =========================================================
# DASHBOARD
# =========================================================
@main.route("/")
@main.route("/admin/panel")
@admin_required
def home():
    try:
        auto_block_high_risk_users()
        stats = get_dashboard_stats()
    except Exception as e:
        logger.error(f"Dashboard load error: {str(e)}")
        stats = {}
    return render_template("admin/dashboard.html", stats=stats)


@main.route("/api/health")
def health_check():
    return jsonify({"status": "success", "message": "RK Trendz MLM Backend Running 🚀"})


@main.route("/test-db")
def test_db():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT NOW() AS server_time")
            result = cur.fetchone()
        return jsonify({"status": "success", "server_time": str(result["server_time"])})
    except Exception as e:
        return jsonify({"status": "error", "message": "Database connection failed"})


# =========================================================
# WALLET API
# =========================================================
@main.route("/api/wallet/<int:user_id>")
@admin_required
def wallet_balance(user_id):
    try:
        with get_cursor() as cur:
            result = get_wallet_balance(cur, user_id)
        return jsonify({"user_id": user_id, "wallet_balance": float(result.get("balance", 0))})
    except Exception as e:
        logger.error(f"Wallet balance error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@main.route("/api/wallet/<int:user_id>/history")
@admin_required
def wallet_history(user_id):
    try:
        with get_cursor() as cur:
            result = get_wallet_history(cur, user_id)
        transactions = result.get("data", []) if isinstance(result, dict) else result
        return jsonify({"user_id": user_id, "transactions": transactions})
    except Exception as e:
        return jsonify({"success": False, "message": "Server error"}), 500


# =========================================================
# P2P TRANSFER (protected)
# =========================================================
@main.route("/api/wallet/transfer", methods=["POST"])
@login_required
def p2p_transfer():
    try:
        import time
        data                = request.get_json()
        receiver_identifier = data.get("receiver")
        amount              = float(data.get("amount", 0))

        if amount <= 0:
            return jsonify({"success": False, "message": "Please enter a valid amount."}), 400

        with get_cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS balance
                FROM wallet_ledger WHERE user_id = %s
            """, (current_user.id,))
            sender_balance = float(cur.fetchone()['balance'])

            if sender_balance < amount:
                return jsonify({"success": False,
                                "message": f"Insufficient funds. Balance: ₹{sender_balance}"}), 400

            cur.execute("""
                SELECT id, full_name FROM users
                WHERE id::text = %s OR email = %s
            """, (str(receiver_identifier), receiver_identifier))
            receiver = cur.fetchone()

            if not receiver:
                return jsonify({"success": False, "message": "Receiver not found."}), 404

            if receiver['id'] == int(current_user.id):
                return jsonify({"success": False, "message": "Cannot transfer to yourself."}), 400

            ref_id = f"p2p_{current_user.id}_to_{receiver['id']}_{int(time.time())}"

            cur.execute("""
                INSERT INTO wallet_ledger
                (user_id, amount, transaction_type, reference_id, description, created_at)
                VALUES (%s, %s, 'p2p_transfer_out', %s, %s, NOW())
            """, (current_user.id, -amount, ref_id,
                  f"Transfer to {receiver['full_name']} (ID: {receiver['id']})"))

            cur.execute("""
                INSERT INTO wallet_ledger
                (user_id, amount, transaction_type, reference_id, description, created_at)
                VALUES (%s, %s, 'p2p_transfer_in', %s, %s, NOW())
            """, (receiver['id'], amount, ref_id,
                  f"Transfer from {current_user.full_name} (ID: {current_user.id})"))

        return jsonify({"success": True,
                        "message": f"Successfully sent ₹{amount} to {receiver['full_name']}!"}), 200
    except Exception as e:
        logger.error(f"Transfer error: {str(e)}")
        return jsonify({"success": False, "message": "Transaction failed."}), 500


# =========================================================
# WITHDRAWAL
# =========================================================
@main.route("/api/wallet/withdraw", methods=["POST"])
@login_required
def request_withdrawal():
    try:
        from app.services.withdraw_service import create_withdraw_request
        data           = request.get_json()
        amount         = data.get("amount")
        payout_method  = data.get("payout_method", "bank")
        payout_details = data.get("payout_details", "")
        if not amount or float(amount) <= 0:
            return jsonify({"status": "error", "message": "Invalid amount"}), 400
        result = create_withdraw_request(current_user.id, float(amount), payout_method, payout_details)
        if result.get("success"):
            return jsonify({"success": True, "message": "Withdrawal requested!"}), 200
        return jsonify({"success": False, "message": result.get("message", "Failed")}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# =========================================================
# TEAM API
# =========================================================
@main.route("/api/team/<int:user_id>")
@admin_required
def team(user_id):
    try:
        with get_cursor() as cur:
            direct_team = get_level_1_team(user_id)
            total_team  = get_total_team_count(user_id)
        return jsonify({"user_id": user_id, "direct_team": direct_team, "total_team": total_team})
    except Exception as e:
        return jsonify({"success": False}), 500


@main.route("/api/genealogy/<int:user_id>")
@admin_required
def genealogy(user_id):
    try:
        tree = get_genealogy_tree(user_id)
        return jsonify({"user_id": user_id, "team_tree": tree})
    except Exception as e:
        return jsonify({"success": False}), 500


# =========================================================
# RANK API
# =========================================================
@main.route("/api/user/rank", methods=["GET"])
@login_required
def get_user_rank_api():
    try:
        from app.services.rank_service import get_user_rank_data
        data = get_user_rank_data(current_user.id)
        return jsonify({"success": True, "data": data}), 200
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to load rank data"}), 500


# =========================================================
# SUPPORT
# =========================================================
@main.route("/api/support/tickets", methods=["GET", "POST"])
@login_required
def manage_support_tickets():
    try:
        with get_cursor() as cur:
            if request.method == "POST":
                data = request.get_json()
                cur.execute("""
                    INSERT INTO support_tickets (user_id, subject, message)
                    VALUES (%s, %s, %s)
                """, (current_user.id, data.get("subject"), data.get("message")))
                return jsonify({"success": True, "message": "Ticket submitted!"}), 200
            else:
                cur.execute("""
                    SELECT id, subject, message, admin_response, status, created_at AS date
                    FROM support_tickets WHERE user_id = %s ORDER BY created_at DESC
                """, (current_user.id,))
                return jsonify({"success": True, "data": cur.fetchall()}), 200
    except Exception as e:
        logger.error(f"Support error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@main.route("/admin/support")
@admin_required
def admin_support():
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT t.*, u.full_name, u.email
                FROM support_tickets t
                JOIN users u ON t.user_id = u.id
                ORDER BY t.created_at DESC
            """)
            tickets = cur.fetchall()
        return render_template("admin/support.html", tickets=tickets)
    except Exception as e:
        flash("Error loading tickets", "danger")
        return redirect("/admin/panel")


@main.route("/admin/support/resolve/<int:ticket_id>", methods=["POST"])
@admin_required
def admin_resolve_ticket(ticket_id):
    try:
        admin_response = request.form.get("admin_response")
        with get_cursor() as cur:
            cur.execute("""
                UPDATE support_tickets
                SET admin_response = %s, status = 'Resolved'
                WHERE id = %s
            """, (admin_response, ticket_id))
        flash("Ticket resolved!", "success")
    except Exception as e:
        flash("Failed to resolve ticket", "danger")
    return redirect("/admin/support")


# =========================================================
# ADMIN TEAM VIEW
# =========================================================
@main.route("/admin/user/team/<int:user_id>")
@admin_required
def admin_user_team(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id, full_name, referral_code, created_at FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
    except Exception:
        user = None

    if not user:
        flash("User not found.", "danger")
        return redirect("/admin/users")

    raw_tree  = get_genealogy_tree(user_id)
    team_tree = {}
    if isinstance(raw_tree, list):
        for row in raw_tree:
            member      = dict(row)
            lvl         = member.get('level', 1)
            member_name = member.get('full_name') or f"User #{member.get('id', '?')}"
            member['full_name'] = member_name
            if lvl not in team_tree:
                team_tree[lvl] = []
            team_tree[lvl].append(member)

    return render_template("admin/user_team.html", user=user, team_tree=team_tree)


# =========================================================
# ADMIN DASHBOARD API
# =========================================================
@main.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    try:
        stats = get_dashboard_stats()
    except Exception:
        stats = {}
    return jsonify({"success": True, "data": stats})


# =========================================================
# USERS
# =========================================================
@main.route("/admin/users")
@admin_required
def admin_users():
    page   = request.args.get("page", 1, type=int)
    search = request.args.get("q", "")
    data   = get_users_paginated(page, search)
    return render_template("admin/users.html",
                           users=data.get("users", []),
                           total=data.get("total", 0),
                           page=data.get("page", 1),
                           pages=data.get("pages", 1),
                           search=search)


@main.route("/admin/user/activate/<int:user_id>", methods=["POST"])
@admin_required
def admin_activate_user(user_id):
    activate_user(user_id)
    flash("User activated successfully", "success")
    return redirect("/admin/users")


@main.route("/admin/user/deactivate/<int:user_id>", methods=["POST"])
@admin_required
def admin_deactivate_user(user_id):
    deactivate_user(user_id)
    flash("User deactivated successfully", "success")
    return redirect("/admin/users")


# =========================================================
# WITHDRAWALS
# =========================================================
@main.route("/admin/withdraws")
@admin_required
def admin_withdraws():
    try:
        requests = get_withdraw_requests()
    except Exception as e:
        logger.error(f"Error loading withdraws: {str(e)}")
        requests = []
    return render_template("admin/withdraw_requests.html", requests=requests)


@main.route("/admin/withdraw/approve/<int:request_id>")
@admin_required
def admin_approve_withdraw(request_id):
    try:
        approve_withdraw(request_id)
        flash("Withdrawal approved successfully!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect("/admin/withdraws")


@main.route("/admin/withdraw/reject/<int:request_id>", methods=['GET', 'POST'])
@admin_required
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
@admin_required
def admin_financial_report():
    try:
        report_data = get_financial_report()
        return render_template("admin/financial_report.html", report=report_data)
    except Exception as e:
        logger.error(f"Report Error: {str(e)}")
        flash("Error generating report", "danger")
        return redirect("/admin/panel")


@main.route("/admin/commission-logs")
@admin_required
def admin_commission_logs():
    page   = request.args.get("page", 1, type=int)
    limit  = 50
    offset = (page - 1) * limit
    logs   = get_commission_logs(limit, offset)
    return render_template("admin/commission_logs.html", logs=logs, page=page)


# =========================================================
# KYC
# =========================================================
@main.route('/api/user/kyc', methods=['GET', 'POST'])
@login_required
def api_user_kyc():
    if request.method == 'GET':
        try:
            with get_cursor() as cur:
                cur.execute("""
                    SELECT kyc_status, kyc_rejection_reason, pan_number,
                           aadhar_number, bank_name, bank_account_no, bank_ifsc
                    FROM users WHERE id = %s
                """, (current_user.id,))
                user_data = cur.fetchone()
            return jsonify({"status": "success", "data": user_data}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    data = request.get_json()
    try:
        with get_cursor() as cur:
            cur.execute("SELECT kyc_status FROM users WHERE id = %s", (current_user.id,))
            status_row     = cur.fetchone()
            current_status = status_row['kyc_status'] if status_row else None
        if current_status in ['approved', 'pending']:
            return jsonify({"status": "error", "message": "KYC locked"}), 400
        result = submit_kyc(user_id=current_user.id, **{
            k: data.get(k) for k in
            ['pan_number', 'aadhar_number', 'bank_name', 'bank_account_no', 'bank_ifsc']
        })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route("/admin/kyc")
@admin_required
def admin_kyc():
    kyc = get_pending_kyc()
    return render_template("admin/kyc_list.html", kyc=kyc)


# =========================================================
# RISK MONITOR
# =========================================================
@main.route("/admin/risk-users")
@admin_required
def admin_risk_users():
    try:
        data = get_risk_dashboard()
        return jsonify({"status": "success", "count": len(data), "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to fetch risk data"}), 500


@main.route("/admin/risk-monitor")
@admin_required
def risk_monitor():
    try:
        risk_filter   = request.args.get("risk")
        status_filter = request.args.get("status")
        search        = request.args.get("q", "").lower()
        risk_data     = get_risk_dashboard()
        filtered_data = []
        for user in risk_data:
            if risk_filter and user["risk_level"] != risk_filter: continue
            if status_filter:
                if status_filter == "active"  and not user["is_active"]: continue
                if status_filter == "blocked" and user["is_active"]:     continue
            if search:
                name  = (user.get("name") or "").lower()
                email = (user.get("email") or "").lower()
                if search not in name and search not in email: continue
            filtered_data.append(user)
        summary = {
            "high":   sum(1 for u in filtered_data if u["risk_level"] == "high"),
            "medium": sum(1 for u in filtered_data if u["risk_level"] == "medium"),
            "low":    sum(1 for u in filtered_data if u["risk_level"] == "low"),
        }
        return render_template("admin/risk_monitor.html",
                               risk_data=filtered_data, summary=summary,
                               filters={"risk": risk_filter, "status": status_filter, "q": search})
    except Exception as e:
        logger.error(f"Risk monitor error: {str(e)}")
        return "Error loading risk panel"


@main.route("/admin/block-user/<int:user_id>", methods=["POST"])
@admin_required
def admin_block_user(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("UPDATE users SET is_active = FALSE WHERE id = %s AND is_active = TRUE", (user_id,))
        flash("User blocked successfully", "danger")
    except Exception as e:
        flash("Error blocking user", "danger")
    return redirect(url_for("main.risk_monitor"))


@main.route("/admin/unblock-user/<int:user_id>", methods=["POST"])
@admin_required
def admin_unblock_user(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("UPDATE users SET is_active = TRUE WHERE id = %s AND is_active = FALSE", (user_id,))
        flash("User unblocked successfully", "success")
    except Exception as e:
        flash("Error unblocking user", "danger")
    return redirect(url_for("main.risk_monitor"))


# =========================================================
# AUTH API (Next.js)
# =========================================================
@main.route("/api/auth/me", methods=["GET"])
def check_session():
    if current_user.is_authenticated:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT is_active FROM users WHERE id = %s", (current_user.id,))
                db_user = cur.fetchone()
                if not db_user or not db_user['is_active']:
                    logout_user()
                    session.clear()
                    return jsonify({"success": False, "message": "Account deactivated."}), 401
        except Exception:
            pass
        return jsonify({"success": True, "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name
        }}), 200
    return jsonify({"success": False, "message": "Unauthorized"}), 401


# =========================================================
# PRODUCT CATALOG
# =========================================================
@main.route("/api/packages", methods=["GET"])
def get_packages():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM subscription_plans WHERE is_active = TRUE ORDER BY price ASC")
            plans       = cur.fetchall()
            backend_url = request.host_url.rstrip('/')
            for p in plans:
                cur.execute("SELECT image_path FROM plan_images WHERE plan_id = %s ORDER BY id DESC LIMIT 1", (p['id'],))
                gallery_img = cur.fetchone()
                raw_img     = gallery_img['image_path'] if gallery_img else p.get('image_url', '')
                p['image_url'] = f"{backend_url}{raw_img}" if raw_img and raw_img.startswith('/') else raw_img
        return jsonify({"success": True, "data": plans}), 200
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to load catalog"}), 500


@main.route("/api/packages/buy", methods=["POST"])
@login_required
def buy_api_package():
    try:
        data    = request.get_json()
        plan_id = data.get("plan_id")
        if not plan_id:
            return jsonify({"success": False, "message": "Plan ID is required"}), 400
        result = purchase_package(current_user.id, plan_id)
        if result.get("success"):
            return jsonify({"success": True, "message": "Plan activated successfully!"}), 200
        return jsonify({"success": False, "message": result.get("message", "Purchase failed")}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "Internal server error"}), 500


@main.route("/api/compensation-plan", methods=["GET"])
def get_compensation_plan():
    try:
        from app.services.package_service import get_global_commissions, get_level_commissions, get_team_target_bonuses
        return jsonify({
            "success": True,
            "global":  get_global_commissions(),
            "levels":  get_level_commissions(),
            "bonuses": get_team_target_bonuses()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to load rules"}), 500


@main.route("/api/user/orders", methods=["GET"])
@login_required
def get_user_orders():
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT up.id AS order_id, up.amount, up.created_at,
                       sp.name AS package_name, sp.lucky_draw_coupons
                FROM user_packages up
                JOIN subscription_plans sp ON up.package_id = sp.id
                WHERE up.user_id = %s ORDER BY up.created_at DESC
            """, (current_user.id,))
            orders = cur.fetchall()
        return jsonify({"success": True, "data": orders}), 200
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to load order history"}), 500


@main.route("/admin/orders")
@admin_required
def admin_purchase_history():
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT up.id AS order_id, up.amount, up.created_at,
                       u.id AS user_id, u.full_name, u.email,
                       sp.name AS plan_name,
                       (SELECT image_path FROM plan_images WHERE plan_id = sp.id LIMIT 1) AS image_url
                FROM user_packages up
                JOIN users u ON up.user_id = u.id
                JOIN subscription_plans sp ON up.package_id = sp.id
                ORDER BY up.created_at DESC
            """)
            orders = cur.fetchall()
        return render_template("admin/orders.html", orders=orders)
    except Exception as e:
        logger.error(f"Orders error: {str(e)}")
        flash("Error loading purchase history.", "danger")
        return redirect("/admin/panel")


# =========================================================
# COMPANY SETTINGS
# BUG FIXED #25: CREATE TABLE removed from request handler.
# Schema must be created via Flask-Migrate, not on every HTTP request.
# =========================================================
@main.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_company_settings():
    try:
        with get_cursor() as cur:
            if request.method == "POST":
                logo_file      = request.files.get("logo_file")
                final_logo_url = request.form.get("existing_logo_url")
                if logo_file and logo_file.filename != '':
                    filename      = secure_filename(logo_file.filename)
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    logo_file.save(os.path.join(upload_folder, filename))
                    final_logo_url = f"/static/uploads/{filename}"

                cur.execute("""
                    UPDATE company_profile SET
                        company_name = %s, head_office_address = %s, branch_address = %s,
                        support_email = %s, support_phone = %s, gst_number = %s, logo_url = %s
                    WHERE id = 1
                """, (
                    request.form.get("company_name"), request.form.get("head_office_address"),
                    request.form.get("branch_address"), request.form.get("support_email"),
                    request.form.get("support_phone"), request.form.get("gst_number"), final_logo_url
                ))
                flash("Company settings updated successfully!", "success")
                return redirect("/admin/settings")

            cur.execute("SELECT * FROM company_profile WHERE id = 1")
            settings = cur.fetchone()
        return render_template("admin/settings.html", settings=settings)
    except Exception as e:
        logger.error(f"Settings error: {str(e)}")
        flash("Error loading settings.", "danger")
        return redirect("/admin/panel")


@main.route("/admin/push-notification/<int:user_id>/<string:notif_type>")
@admin_required
def push_manual_notification(user_id, notif_type):
    try:
        message = f"System triggered {notif_type} alert for User #{user_id}"
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO notification_logs (user_id, notification_type, message)
                VALUES (%s, %s, %s)
            """, (user_id, notif_type, message))
        flash(f"{notif_type.capitalize()} alert pushed successfully!", "success")
    except Exception as e:
        logger.error(f"Notification error: {str(e)}")
        flash("Failed to push notification.", "danger")
    return redirect(request.referrer or "/admin/users")


@main.route("/admin/user/network/<int:user_id>")
@admin_required
def admin_user_network(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT u.id, u.full_name, u.email, u.phone, u.created_at AS vintage,
                       u.referral_code, s.id AS sponsor_id, s.full_name AS sponsor_name
                FROM users u
                LEFT JOIN users s ON u.sponsor_id = s.id
                WHERE u.id = %s
            """, (user_id,))
            user_info = cur.fetchone()

            if not user_info:
                flash("User not found.", "danger")
                return redirect("/admin/panel")

            try:
                from app.services.rank_service import get_user_rank_data
                rank_data = get_user_rank_data(user_id)
                user_info['rank_name'] = rank_data.get('current_rank', 'Distributor') if isinstance(rank_data, dict) else 'Distributor'
            except Exception:
                user_info['rank_name'] = 'Distributor'

            cur.execute("""
                SELECT sp.name AS plan_name, up.amount, up.created_at AS bought_at
                FROM user_packages up
                JOIN subscription_plans sp ON up.package_id = sp.id
                WHERE up.user_id = %s ORDER BY up.created_at DESC
            """, (user_id,))
            plans = cur.fetchall()

            cur.execute("""
                SELECT id, full_name, created_at, phone, referral_code
                FROM users WHERE sponsor_id = %s ORDER BY created_at DESC
            """, (user_id,))
            downlines = cur.fetchall()

        return render_template("admin/network_profile.html",
                               user=user_info, plans=plans, downlines=downlines)
    except Exception as e:
        logger.error(f"Network Profile Error: {str(e)}")
        flash("Failed to load user profile.", "danger")
        return redirect("/admin/panel")


# =========================================================
# BUG FIXED #21 #22 #23: UNPROTECTED TEST ROUTES REMOVED
# These routes allowed anyone to credit/debit wallets without authentication:
#   /test/credit/<user_id>/<amount>
#   /test/create-withdraw/<user_id>/<amount>
#   /test/clear-withdraw/<user_id>
# They are DELETED. Use a proper test suite (pytest) instead.
# =========================================================

@main.route("/test-route")
def test_route():
    return "Working"


# =========================================================
# RANK MANAGEMENT UI
# =========================================================
@main.route("/admin/ranks")
@admin_required
def admin_ranks_page():
    return render_template("admin/ranks.html")
