from flask import Blueprint, request, jsonify, session
from app.services.user_service import register_new_member, authenticate_user

# Create the "Blueprint" which tells Flask these are the Auth URLs
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

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

    # 3. Return Standardized HTTP Status Codes
    if result['status'] == 'success':
        return jsonify(result), 201 # 201 means "Created successfully"
    else:
        return jsonify(result), 400 # 400 means "Bad Request" (e.g., email exists)

# -----------------------------------
# Secure Login Route
# -----------------------------------
@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Enterprise API: Verifies credentials and creates a secure Server-Side Session.
    Endpoint: POST /api/auth/login
    """
    data = request.get_json()

    # 1. Validate Input
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    # 2. Authenticate via Service
    result = authenticate_user(data['email'], data['password'])

    if result['status'] == 'success':
        user = result['user']
        
        # 3. Create a secure session (Stores an encrypted cookie on the user's browser)
        session['user_id'] = user['id']
        session['role_id'] = user['role_id']

        # 4. Filter the data (NEVER send the whole database row back to the front-end)
        safe_user_data = {
            "id": user['id'],
            "full_name": user['full_name'],
            "email": user['email'],
            "role_id": user['role_id']
        }
        
        return jsonify({
            "status": "success", 
            "message": "Login successful", 
            "user": safe_user_data
        }), 200
    else:
        return jsonify(result), 401 # 401 means "Unauthorized"

# -----------------------------------
# Secure Logout Route
# -----------------------------------
@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    """
    Enterprise API: Destroys the secure session.
    Endpoint: POST /api/auth/logout
    """
    session.clear() # Wipes the user's secure cookie
    return jsonify({"status": "success", "message": "Logged out successfully."}), 200
