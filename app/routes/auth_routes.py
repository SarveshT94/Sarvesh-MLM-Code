from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, UserMixin
from app.services.user_service import register_new_member, authenticate_user

# Create the "Blueprint" which tells Flask these are the Auth URLs
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# --- Enterprise Flask-Login Wrapper ---
# Flask-Login requires a class object to manage sessions securely. 
# We create a fast, lightweight wrapper for your raw database dictionary here.
class AuthUser(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict['id']) # Flask-Login strictly requires the ID to be a string
        self.role_id = user_dict.get('role_id', 2)
        self.full_name = user_dict.get('full_name', '')
        self.email = user_dict.get('email', '')

# -----------------------------------
# Secure Registration Route
# -----------------------------------
@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Enterprise API: Validates incoming web data before sending it to the Gatekeeper.
    Endpoint: POST /api/auth/register
    """
    data = request.get_json()

    # 1. Strict Input Validation (Traffic Cop)
    required_fields = ['full_name', 'email', 'phone', 'password']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields."}), 400

    sponsor_id = data.get('sponsor_id') # Sponsor is optional for the top company account

    # 2. Process via our Secure Service
    result = register_new_member(
        full_name=data['full_name'],
        email=data['email'],
        phone=data['phone'],
        raw_password=data['password'],
        sponsor_id=sponsor_id
    )

    if result['status'] == 'success':
        return jsonify(result), 201 
    else:
        return jsonify(result), 400 

# -----------------------------------
# Secure Login Route
# -----------------------------------
@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Enterprise API: Verifies credentials and officially logs the user into the Flask Server.
    Endpoint: POST /api/auth/login
    """
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    # 1. Authenticate via your flawless Service
    result = authenticate_user(data['email'], data['password'])

    if result['status'] == 'success':
        user_dict = result['user']

        # 2. Enterprise Security: Log them into Flask-Login
        # This creates the encrypted, HttpOnly cookie automatically!
        user_obj = AuthUser(user_dict)
        login_user(user_obj)

        # (Optional) Keep manual session for legacy routes that haven't been upgraded yet
        session['user_id'] = user_dict['id']
        session['role_id'] = user_dict['role_id']

        # 3. Filter the data (Never send the whole database row back)
        safe_user_data = {
            "id": user_dict['id'],
            "full_name": user_dict['full_name'],
            "email": user_dict['email'],
            "role_id": user_dict['role_id']
        }

        return jsonify({
            "status": "success",
            "message": "Login successful",
            "user": safe_user_data
        }), 200
    else:
        return jsonify(result), 401 

# -----------------------------------
# Secure Logout Route
# -----------------------------------
@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    """
    Enterprise API: Safely destroys both Flask-Login and legacy sessions.
    Endpoint: POST /api/auth/logout
    """
    logout_user()  # Destroys the Flask-Login secure cookie
    session.clear() # Wipes any legacy session data
    return jsonify({"status": "success", "message": "Logged out successfully."}), 200
