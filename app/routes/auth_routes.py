from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, UserMixin
from app.services.user_service import register_new_member, authenticate_user
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

        # ✅ Strict Input Validation
        required_fields = ['full_name', 'email', 'phone', 'password']
        if not data or not all(field in data for field in required_fields):
            return jsonify({
                "status": "error",
                "message": "Missing required fields."
            }), 400

        sponsor_id = data.get('sponsor_id')

        # ✅ Call Service Layer
        result = register_new_member(
            full_name=data['full_name'],
            email=data['email'],
            phone=data['phone'],
            raw_password=data['password'],
            sponsor_id=sponsor_id
        )

        if result['status'] == 'success':
            logger.info(f"User registered: {data['email']}")
            return jsonify(result), 201
        else:
            logger.warning(f"Registration failed: {result}")
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500


# -----------------------------------
# Secure Login Route
# -----------------------------------
@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    try:
        data = request.get_json()

        # ✅ Input Validation
        if not data:
            return jsonify({
                "status": "error",
                "message": "No input data provided."
            }), 400

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                "status": "error",
                "message": "Email and password are required."
            }), 400

        # ✅ Authenticate via Service
        result = authenticate_user(email, password)

        if result['status'] == 'success':
            user_dict = result['user']

            # ✅ Flask-Login session
            user_obj = AuthUser(user_dict)
            login_user(user_obj)

            # ✅ Legacy session (kept for compatibility)
            session['user_id'] = user_dict['id']
            session['role_id'] = user_dict['role_id']

            # ✅ Safe response data
            safe_user_data = {
                "id": user_dict['id'],
                "full_name": user_dict.get('full_name', ''),
                "email": user_dict.get('email', ''),
                "role_id": user_dict.get('role_id', 2)
            }

            logger.info(f"User logged in: {email}")

            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": safe_user_data
            }), 200

        else:
            logger.warning(f"Failed login attempt: {email}")
            return jsonify(result), 401

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500


# -----------------------------------
# Secure Logout Route
# -----------------------------------
@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    try:
        logout_user()
        session.clear()

        logger.info("User logged out")

        return jsonify({
            "status": "success",
            "message": "Logged out successfully."
        }), 200

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Logout failed"
        }), 500
