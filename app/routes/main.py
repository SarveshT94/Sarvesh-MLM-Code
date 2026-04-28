from flask import Blueprint, render_template, request, redirect, jsonify, flash, url_for, session
from flask_login import login_required, current_user, login_user, logout_user
import logging
import inspect 
import os
from werkzeug.utils import secure_filename
from flask import current_app
from functools import wraps 

from app.db import get_cursor
from app.services.user_service import authenticate_user 

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
# 🔒 ADMIN SECURITY WRAPPER
# =========================================================
def admin_required(f):
    """Protects admin routes from unauthorized access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, 'role_id', 2) != 1:
            flash("Unauthorized. Please log in as an Admin.", "danger")
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated_function


# =========================================================
# 🔥 INTELLIGENT SERVICE EXECUTOR
# =========================================================
def execute_service(func, user_id):
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    if len(params) > 0 and params[0] in ['cur', 'cursor']:
        with get_cursor() as cur:
            return func(cur, user_id)
    else:
        return func(user_id)


# =========================================================
# 🔑 ADMIN LOGIN & LOGOUT ROUTES
# =========================================================
@main.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated and getattr(current_user, 'role_id', 2) == 1:
        return redirect("/admin/panel")

    if request.method == "POST":
        identifier = request.form.get("identifier")
        password = request.form.get("password")
        
        result = authenticate_user(identifier, password)
        
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
# 🔥 HOME & DASHBOARD 
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
# 🔧 WALLET API
# =========================================================
@main.route("/api/wallet/<int:user_id>")
def wallet_balance(user_id):
    try:
        result = execute_service(get_wallet_balance, user_id)
        if isinstance(result, dict):
            balance = result.get("balance", 0)
        elif isinstance(result, (int, float)):
            balance = result
        else:
            balance = 0
            
        return jsonify({"user_id": user_id, "wallet_balance": float(balance)})
    except Exception as e:
        logger.error(f"Wallet balance error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@main.route("/api/wallet/<int:user_id>/history")
def wallet_history(user_id):
    try:
        result = execute_service(get_wallet_history, user_id)
        if isinstance(result, dict):
            transactions = result.get("data", [])
        elif isinstance(result, list):
            transactions = result
        else:
            transactions = []
            
        return jsonify({"user_id": user_id, "transactions": transactions})
    except Exception as e:
        logger.error(f"Wallet history error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


# =========================================================
# 💸 SECURE P2P FUND TRANSFER API
# =========================================================
@main.route("/api/wallet/transfer", methods=["POST"])
def p2p_transfer():
    try:
        import time
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        data = request.get_json()
        receiver_identifier = data.get("receiver") 
        amount = float(data.get("amount", 0))

        if amount <= 0:
            return jsonify({"success": False, "message": "Please enter a valid amount."}), 400

        with get_cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(amount), 0) as balance FROM wallet_ledger WHERE user_id = %s", (current_user.id,))
            sender_balance = float(cur.fetchone()['balance'])

            if sender_balance < amount:
                return jsonify({"success": False, "message": f"Insufficient funds. Your balance is ₹{sender_balance}"}), 400

            cur.execute("SELECT id, full_name FROM users WHERE id::text = %s OR email = %s", (str(receiver_identifier), receiver_identifier))
            receiver = cur.fetchone()

            if not receiver:
                return jsonify({"success": False, "message": "Receiver not found. Check the ID or Email."}), 404
            
            if receiver['id'] == current_user.id:
                return jsonify({"success": False, "message": "You cannot transfer funds to yourself."}), 400

            ref_id = f"p2p_{current_user.id}_to_{receiver['id']}_{int(time.time())}"
            
            cur.execute("""
                INSERT INTO wallet_ledger (user_id, amount, transaction_type, reference_id, description, created_at)
                VALUES (%s, %s, 'p2p_transfer_out', %s, %s, NOW())
            """, (current_user.id, -amount, ref_id, f"Fund transfer to {receiver['full_name']} (ID: {receiver['id']})"))

            cur.execute("""
                INSERT INTO wallet_ledger (user_id, amount, transaction_type, reference_id, description, created_at)
                VALUES (%s, %s, 'p2p_transfer_in', %s, %s, NOW())
            """, (receiver['id'], amount, ref_id, f"Fund received from {current_user.full_name} (ID: {current_user.id})"))

        return jsonify({"success": True, "message": f"Successfully sent ₹{amount} to {receiver['full_name']}!"}), 200

    except Exception as e:
        logger.error(f"Transfer API Error: {str(e)}")
        return jsonify({"success": False, "message": "Transaction failed."}), 500

# =========================================================
# 💰 SECURE USER WITHDRAWAL API
# =========================================================
@main.route("/api/wallet/withdraw", methods=["POST"])
def request_withdrawal():
    try:
        from app.services.withdraw_service import create_withdraw_request
        if not current_user.is_authenticated:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
            
        data = request.get_json()
        amount = data.get("amount")
        payout_method = data.get("payout_method", "bank")
        payout_details = data.get("payout_details", "")
        
        if not amount or float(amount) <= 0:
            return jsonify({"status": "error", "message": "Invalid amount"}), 400
        
        result = create_withdraw_request(current_user.id, float(amount), payout_method, payout_details)
        
        if result.get("success") or result.get("status") == "success":
            return jsonify({"success": True, "message": "Withdrawal requested successfully!"}), 200
            
        return jsonify({"success": False, "message": result.get("message", "Failed")}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# =========================================================
# 🔧 TEAM API
# =========================================================
@main.route("/api/team/<int:user_id>")
def team(user_id):
    try:
        direct_team = execute_service(get_level_1_team, user_id)
        total_team = execute_service(get_total_team_count, user_id)
        return jsonify({"user_id": user_id, "direct_team": direct_team, "total_team": total_team})
    except Exception as e:
        logger.error(f"Team error: {str(e)}")
        return jsonify({"success": False}), 500

@main.route("/api/genealogy/<int:user_id>")
def genealogy(user_id):
    try:
        tree = execute_service(get_genealogy_tree, user_id)
        return jsonify({"user_id": user_id, "team_tree": tree})
    except Exception as e:
        logger.error(f"Genealogy error: {str(e)}")
        return jsonify({"success": False}), 500


# =========================================================
# 🔥 GAMIFICATION & RANK API
# =========================================================
@main.route("/api/user/rank", methods=["GET"])
def get_user_rank_api():
    try:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Unauthorized"}), 401
            
        from app.services.rank_service import get_user_rank_data
        data = get_user_rank_data(current_user.id)
        return jsonify({"success": True, "data": data}), 200
    except Exception as e:
        logger.error(f"Rank API Error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load rank data"}), 500


# =========================================================
# 🔥 USER SUPPORT TICKET API
# =========================================================
@main.route("/api/support/tickets", methods=["GET", "POST"])
def manage_support_tickets():
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
        
    try:
        with get_cursor() as cur:
            if request.method == "POST":
                data = request.get_json()
                cur.execute("""
                    INSERT INTO support_tickets (user_id, subject, message) 
                    VALUES (%s, %s, %s)
                """, (current_user.id, data.get("subject"), data.get("message")))
                return jsonify({"success": True, "message": "Ticket submitted successfully!"}), 200
            else:
                cur.execute("""
                    SELECT id, subject, message, admin_response, status, created_at as date 
                    FROM support_tickets WHERE user_id = %s ORDER BY created_at DESC
                """, (current_user.id,))
                return jsonify({"success": True, "data": cur.fetchall()}), 200
    except Exception as e:
        logger.error(f"Support API Error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# =========================================================
# 🔥 ADMIN PANEL SUPPORT ROUTES
# =========================================================
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
        flash("Ticket resolved and updated!", "success")
    except Exception as e:
        flash("Failed to resolve ticket", "danger")
    return redirect("/admin/support")


# =========================================================
# 🔥 ADMIN TEAM VIEW
# =========================================================
@main.route("/admin/user/team/<int:user_id>")
@admin_required
def admin_user_team(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("SELECT id, full_name, referral_code,  created_at FROM users WHERE id = %s", (user_id,))
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


# ----------------------------------
# ADMIN WITHDRAW QUEUE
# ----------------------------------
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
        # Get the fresh data we see in the terminal
        report_data = get_financial_report()
        
        # Explicitly pass ONLY the report object to clear the cache
        return render_template("admin/financial_report.html", report=report_data)
    except Exception as e:
        logger.error(f"Report Error: {str(e)}")
        return redirect("/admin/panel")


@main.route("/admin/commission-logs")
@admin_required
def admin_commission_logs():
    page = request.args.get("page", 1, type=int)
    limit = 50
    offset = (page - 1) * limit
    logs = get_commission_logs(limit, offset)
    return render_template("admin/commission_logs.html", logs=logs, page=page)


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
                user_id=current_user.id, pan_number=data.get('pan_number'),
                aadhar_number=data.get('aadhar_number'), bank_name=data.get('bank_name'),
                bank_account_no=data.get('bank_account_no'), bank_ifsc=data.get('bank_ifsc')
            )
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@main.route("/admin/kyc")
@admin_required
def admin_kyc():
    kyc = get_pending_kyc()
    return render_template("admin/kyc_list.html", kyc=kyc)


# =========================================================
# 🚨 RISK MONITOR API & PAGE
# =========================================================
@main.route("/admin/risk-users")
@admin_required
def admin_risk_users():
    try:
        data = get_risk_dashboard()
        return jsonify({"status": "success", "count": len(data), "data": data})
    except Exception as e:
        logger.error(f"Risk API error: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to fetch risk data"}), 500

@main.route("/admin/risk-monitor")
@admin_required
def risk_monitor():
    try:
        risk_filter = request.args.get("risk")
        status_filter = request.args.get("status")
        search = request.args.get("q", "").lower()

        risk_data = get_risk_dashboard()

        filtered_data = []
        for user in risk_data:
            if risk_filter and user["risk_level"] != risk_filter: continue
            if status_filter:
                if status_filter == "active" and not user["is_active"]: continue
                if status_filter == "blocked" and user["is_active"]: continue
            if search:
                name = (user.get("name") or "").lower()
                email = (user.get("email") or "").lower()
                if search not in name and search not in email: continue
            filtered_data.append(user)

        summary = {
            "high": sum(1 for u in filtered_data if u["risk_level"] == "high"),
            "medium": sum(1 for u in filtered_data if u["risk_level"] == "medium"),
            "low": sum(1 for u in filtered_data if u["risk_level"] == "low"),
        }

        return render_template(
            "admin/risk_monitor.html", risk_data=filtered_data,
            summary=summary, filters={"risk": risk_filter, "status": status_filter, "q": search}
        )
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
# 🔐 AUTHENTICATION API (For Next.js)
# =========================================================
@main.route("/api/auth/me", methods=["GET"])
def check_session():
    if current_user.is_authenticated:
        # 🔥 FIXED: Real-time DB check so deactivated users get booted from the frontend!
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


# =========================================================
# 🛒 PRODUCT CATALOG API (🔥 FIXED FOR NEXT.JS IMAGES)
# =========================================================
@main.route("/api/packages", methods=["GET"])
def get_packages():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM subscription_plans WHERE is_active = TRUE ORDER BY price ASC")
            plans = cur.fetchall()
            
            backend_url = request.host_url.rstrip('/')
            
            for p in plans:
                cur.execute("SELECT image_path FROM plan_images WHERE plan_id = %s ORDER BY id DESC LIMIT 1", (p['id'],))
                gallery_img = cur.fetchone()
                
                raw_img = gallery_img['image_path'] if gallery_img else p.get('image_url', '')
                
                # Attach the full backend URL so Next.js can pull the image
                if raw_img and raw_img.startswith('/'):
                    p['image_url'] = f"{backend_url}{raw_img}"
                else:
                    p['image_url'] = raw_img
                    
        return jsonify({"success": True, "data": plans}), 200
    except Exception as e:
        logger.error(f"Error fetching packages: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load catalog"}), 500


@main.route("/api/packages/buy", methods=["POST"])
def buy_api_package():
    try:
        from app.services.package_service import purchase_package
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Unauthorized"}), 401
            
        data = request.get_json()
        plan_id = data.get("plan_id")
        if not plan_id:
            return jsonify({"success": False, "message": "Plan ID is required"}), 400
            
        result = purchase_package(current_user.id, plan_id)
        if result.get("success"):
            return jsonify({"success": True, "message": "Plan activated successfully!"}), 200
        else:
            return jsonify({"success": False, "message": result.get("message", "Purchase failed")}), 400
    except Exception as e:
        logger.error(f"Purchase API Error: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


# =========================================================
# 📊 DYNAMIC COMPENSATION PLAN API
# =========================================================
@main.route("/api/compensation-plan", methods=["GET"])
def get_compensation_plan():
    try:
        from app.services.package_service import get_global_commissions, get_level_commissions, get_team_target_bonuses
        return jsonify({
            "success": True,
            "global": get_global_commissions(),
            "levels": get_level_commissions(),
            "bonuses": get_team_target_bonuses()
        }), 200
    except Exception as e:
        logger.error(f"Error fetching compensation plan: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load rules"}), 500


# =========================================================
# 📦 USER ORDERS & PURCHASE HISTORY
# =========================================================
@main.route("/api/user/orders", methods=["GET"])
def get_user_orders():
    try:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        with get_cursor() as cur:
            cur.execute("""
                SELECT up.id AS order_id, up.amount, up.created_at, sp.name AS package_name, sp.lucky_draw_coupons
                FROM user_packages up
                JOIN subscription_plans sp ON up.package_id = sp.id
                WHERE up.user_id = %s ORDER BY up.created_at DESC
            """, (current_user.id,))
            orders = cur.fetchall()
        return jsonify({"success": True, "data": orders}), 200
    except Exception as e:
        logger.error(f"Error fetching orders: {str(e)}")
        return jsonify({"success": False, "message": "Failed to load order history"}), 500

@main.route("/admin/orders")
@admin_required
def admin_purchase_history():
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT up.id as order_id, up.amount, up.created_at, u.id as user_id, u.full_name, u.email,
                       sp.name as plan_name, (SELECT image_path FROM plan_images WHERE plan_id = sp.id LIMIT 1) as image_url
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
# 🔥 COMPANY PROFILE SETTINGS
# =========================================================
@main.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_company_settings():
    try:
        with get_cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS company_profile (
                    id SERIAL PRIMARY KEY, company_name VARCHAR(255), head_office_address TEXT,
                    branch_address TEXT, support_email VARCHAR(255), support_phone VARCHAR(50),
                    gst_number VARCHAR(100), logo_url VARCHAR(255)
                )
            """)
            
            cur.execute("SELECT COUNT(*) as count FROM company_profile WHERE id = 1")
            if cur.fetchone()['count'] == 0:
                cur.execute("INSERT INTO company_profile (id, company_name) VALUES (1, 'RK Trendz')")

            if request.method == "POST":
                logo_file = request.files.get("logo_file")
                final_logo_url = request.form.get("existing_logo_url")
                
                if logo_file and logo_file.filename != '':
                    filename = secure_filename(logo_file.filename)
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filepath = os.path.join(upload_folder, filename)
                    logo_file.save(filepath)
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


# =========================================================
# 🔥 MANUAL NOTIFICATION PUSHER
# =========================================================
@main.route("/admin/push-notification/<int:user_id>/<string:notif_type>")
@admin_required
def push_manual_notification(user_id, notif_type):
    try:
        message = f"System triggered {notif_type} alert for User #{user_id}"
        with get_cursor() as cur:
            cur.execute("INSERT INTO notification_logs (user_id, notification_type, message) VALUES (%s, %s, %s)", (user_id, notif_type, message))
        flash(f"{notif_type.capitalize()} alert pushed successfully to User RKT-{user_id:05d}!", "success")
        return redirect(request.referrer or "/admin/users")
    except Exception as e:
        logger.error(f"Notification error: {str(e)}")
        flash("Failed to push notification.", "danger")
        return redirect(request.referrer or "/admin/users")


# =========================================================
# 🔥 360° USER NETWORK PROFILE
# =========================================================
@main.route("/admin/user/network/<int:user_id>")
@admin_required
def admin_user_network(user_id):
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT u.id, u.full_name, u.email, u.phone, u.created_at as vintage, u.referral_code,
                       s.id as sponsor_id, s.full_name as sponsor_name
                FROM users u
                LEFT JOIN users s ON u.sponsor_id = s.id
                WHERE u.id = %s
            """, (user_id,))
            user_info = cur.fetchone()

            if not user_info:
                flash("User not found in system.", "danger")
                return redirect(request.referrer or "/admin/panel")

            try:
                from app.services.rank_service import get_user_rank_data
                rank_data = get_user_rank_data(user_id)
                user_info['rank_name'] = rank_data.get('rank_name', rank_data.get('current_rank', 'Distributor')) if isinstance(rank_data, dict) else 'Distributor'
            except Exception:
                user_info['rank_name'] = 'Distributor'

            cur.execute("""
                SELECT sp.name as plan_name, up.amount, up.created_at as bought_at
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

        return render_template("admin/network_profile.html", user=user_info, plans=plans, downlines=downlines)
    except Exception as e:
        logger.error(f"Network Profile Error: {str(e)}")
        flash("Failed to load user profile.", "danger")
        return redirect(request.referrer or "/admin/panel")


#______________________________________________________
# YOUR CUSTOM TEST DB ROUTES
#______________________________________________________
@main.route("/test/credit/<int:user_id>/<int:amount>")
def test_credit(user_id, amount):
    try:
        from app.services.wallet_service import credit_wallet
        from datetime import datetime
        with get_cursor() as cur:
            reference = f"test_credit_{user_id}_{datetime.utcnow().timestamp()}"
            credit_wallet(cur, user_id, amount, reference=reference, description="Test credit")
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
            cur.execute("DELETE FROM withdraw_requests WHERE user_id = %s", (user_id,))
        return "✅ Cleared withdraw requests"
    except Exception as e:
        return str(e)

@main.route("/test-route")
def test_route():
    return "Working"
