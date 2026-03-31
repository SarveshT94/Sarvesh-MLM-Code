from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user
from app.services.user_service import register_user
from app.services.activation_service import activate_user
from app.utils.security import verify_password
from app.db import get_cursor

# ✅ API PREFIX (VERY IMPORTANT)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# -------------------------------
# USER CLASS (Flask-Login)
# -------------------------------
class User:
    def __init__(self, user_data):
        self.id = str(user_data['id'])
        self.phone = user_data.get('phone')
        self.role_id = user_data.get('role_id')

    def is_authenticated(self): return True
    def is_active(self): return True
    def is_anonymous(self): return False
    def get_id(self): return self.id


# -------------------------------
# REGISTER USER
# -------------------------------
@auth_bp.route("/register", methods=["POST", "OPTIONS"])
def register():

    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json()
        print("REGISTER DATA:", data)   # 🔥 DEBUG

        full_name = data.get("full_name")
        email = data.get("email")
        phone = data.get("phone")
        password = data.get("password")
        referral_code = data.get("referral_code")

        # ✅ PHONE VALIDATION (ADD HERE)
        if phone and "@" in phone:
            return jsonify({
                "success": False,
                "message": "Enter valid phone number, not email"
            }), 400    
        
        if not full_name or not phone or not password:
            return jsonify({
                "success": False,
                "message": "Required fields missing"
            }), 400

        result = register_user(
            full_name=full_name,
            email=email,
            phone=phone,
            password=password,
            referral_code=referral_code
        )

        print("REGISTER RESULT:", result)   # 🔥 DEBUG

        if not result["success"]:
            return jsonify(result), 400

        return jsonify({
            "success": True,
            "message": "User registered successfully",
            "user_id": result["user_id"],
            "referral_code": result["referral_code"]
        })

    except Exception as e:
        print("🔥 REGISTER CRASH:", str(e))   # ✅ REAL ERROR मिलेगा
        return jsonify({
            "success": False,
            "message": "Server error",
            "error": str(e)
        }), 500

# -------------------------------
# LOGIN USER
# -------------------------------
@auth_bp.route("/login", methods=["POST", "OPTIONS"])
def login():

    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")

    with get_cursor() as cur:

        # ✅ email या phone दोनों support
        if email:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        else:
            cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))

        user = cur.fetchone()

    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    if not verify_password(user["password_hash"], password):
        return jsonify({"success": False, "message": "Invalid password"}), 401

    login_user(User(user))

    session.permanent = True
    session['user_id'] = user["id"]

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "phone": user.get("phone"),
            "email": user.get("email"),
            "role_id": user.get("role_id")
        },
        "token": "dummy-token"  # 🔥 अभी के लिए (later JWT)
    })


# -------------------------------
# LOGOUT
# -------------------------------
@auth_bp.route("/logout", methods=["GET"])
def logout():
    logout_user()
    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    })


# -------------------------------
# ACTIVATE USER
# -------------------------------
@auth_bp.route("/activate", methods=["POST", "OPTIONS"])
def activate():

    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "message": "Invalid JSON data"
        }), 400

    user_id = data.get("user_id")
    purchase_amount = data.get("amount")

    if not user_id or not purchase_amount:
        return jsonify({
            "success": False,
            "message": "user_id and amount required"
        }), 400

    try:
        purchase_amount = float(purchase_amount)
    except ValueError:
        return jsonify({
            "success": False,
            "message": "Amount must be numeric"
        }), 400

    result = activate_user(user_id, purchase_amount)

    if not result["success"]:
        return jsonify(result), 400

    return jsonify(result), 200
