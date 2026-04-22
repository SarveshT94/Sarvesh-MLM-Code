from flask import Blueprint, request, jsonify, session
from app.services.otp_service import create_and_send_otp, verify_and_update_profile
import logging

logger = logging.getLogger(__name__)

# Create a new blueprint for profile-related routes
profile_bp = Blueprint('profile', __name__, url_prefix='/api/profile')

# Security Decorator: Ensures the user is logged in before they can change profile data
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"status": "error", "message": "Unauthorized access. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------------
# Route 1: Request an OTP to change Email/Phone
# -----------------------------------
@profile_bp.route('/request-update', methods=['POST'])
@login_required
def request_update():
    try:
        data = request.get_json()
        identifier_type = data.get('type')  # Expecting 'email' or 'phone'
        new_identifier = data.get('new_identifier')

        if not identifier_type or not new_identifier:
            return jsonify({"status": "error", "message": "Type and new identifier are required."}), 400

        user_id = session['user_id']
        result = create_and_send_otp(user_id, identifier_type, new_identifier)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        return jsonify(result), 400

    except Exception as e:
        logger.error(f"Profile update request error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

# -----------------------------------
# Route 2: Verify the OTP and save the change
# -----------------------------------
@profile_bp.route('/verify-otp', methods=['POST'])
@login_required
def verify_otp():
    try:
        data = request.get_json()
        otp_code = data.get('otp_code')

        if not otp_code:
            return jsonify({"status": "error", "message": "OTP is required."}), 400

        user_id = session['user_id']
        result = verify_and_update_profile(user_id, otp_code)

        if result['status'] == 'success':
            return jsonify(result), 200
        return jsonify(result), 400

    except Exception as e:
        logger.error(f"OTP verification error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
