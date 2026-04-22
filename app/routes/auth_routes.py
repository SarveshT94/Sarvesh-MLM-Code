from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, UserMixin
from app.services.user_service import (
    register_new_member, 
    authenticate_user, 
    process_forgot_password, 
    process_reset_password
)
import logging
from app import limiter

# Logger setup
logger = logging.getLogger(__name__)

# Create the "Blueprint"
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# --- Enterprise Flask-Login Wrapper ---
class AuthUser(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict['id'])
        self.role_id = user_dict.get('role_id', 2)
        self.full_name = user_dict.get('full_name', '')
        self.email = user_dict.get('email', '')


# -----------------------------------
# Secure Registration Route
# -----------------------------------
@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()

        required_fields = ['full_name', 'email', 'phone', 'password']
        if not data or not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": "Missing required fields."}), 400

        clean_email = data['email'].strip().lower()
        clean_phone = data['phone'].strip()
        sponsor_id = data.get('sponsor_id')

        result = register_new_member(
            full_name=data['full_name'],
            email=clean_email,
            phone=clean_phone,
            raw_password=data['password'],
            sponsor_id=sponsor_id
        )

        if result['status'] == 'success':
            logger.info(f"User registered: {clean_email}")
            return jsonify(result), 201
        return jsonify(result), 400

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# -----------------------------------
# Secure Login Route
# -----------------------------------
@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No input data provided."}), 400

        # Look for either 'identifier' or fallback to 'email' if old frontend sends it
        identifier = data.get('identifier') or data.get('email')
        password = data.get('password')

        if not identifier or not password:
            return jsonify({"status": "error", "message": "Email/Phone and password are required."}), 400

        result = authenticate_user(identifier, password)

        if result['status'] == 'success':
            user_dict = result['user']
            user_obj = AuthUser(user_dict)
            login_user(user_obj)
            session['user_id'] = user_dict['id']
            session['role_id'] = user_dict['role_id']

            return jsonify({
                "status": "success", "message": "Login successful", "user": user_dict
            }), 200

        return jsonify(result), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

# -----------------------------------
# Secure Logout Route
# -----------------------------------
@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    try:
        logout_user()
        session.clear()
        logger.info("User logged out")
        return jsonify({"status": "success", "message": "Logged out successfully."}), 200
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({"status": "error", "message": "Logout failed"}), 500


# -----------------------------------
# Forgot Password Route
# -----------------------------------
@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    try:
        data = request.get_json()
        identifier = data.get('identifier') or data.get('email')

        if not identifier:
            return jsonify({"status": "error", "message": "Email or Phone is required."}), 400

        result = process_forgot_password(identifier)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Forgot password route error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

# -----------------------------------
# Reset Password Route
# -----------------------------------
@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    try:
        data = request.get_json()
        token = data.get('token')
        new_password = data.get('password')

        if not token or not new_password:
            return jsonify({"status": "error", "message": "Token and new password are required."}), 400

        if len(new_password) < 6:
            return jsonify({"status": "error", "message": "Password must be at least 6 characters long."}), 400

        result = process_reset_password(token, new_password)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        return jsonify(result), 400

    except Exception as e:
        logger.error(f"Reset password route error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# -----------------------------------
# Session Verification Route (/me)
# -----------------------------------
@auth_bp.route('/me', methods=['GET'])
def get_me():
    from flask_login import current_user
    try:
        if current_user.is_authenticated:
            return jsonify({
                "status": "success",
                "user": {
                    "id": current_user.id,
                    "full_name": current_user.full_name,
                    "email": current_user.email,
                    "role_id": current_user.role_id,
                    # We securely grab these from the updated User class
                    "phone": getattr(current_user, 'phone', ''),
                    "referral_code": getattr(current_user, 'referral_code', '')
                }
            }), 200
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    except Exception as e:
        logger.error(f"Session check error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
