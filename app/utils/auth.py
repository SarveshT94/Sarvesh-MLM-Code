from functools import wraps
from flask import session, jsonify


# -------------------------------
# Login Required (for all users)
# -------------------------------
def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return jsonify({
                "success": False,
                "message": "Login required"
            }), 401

        return f(*args, **kwargs)

    return decorated_function


# -------------------------------
# Admin Required (for admin APIs)
# -------------------------------
def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return jsonify({
                "success": False,
                "message": "Login required"
            }), 401

        # check admin role
        if session.get("role") != "admin":
            return jsonify({
                "success": False,
                "message": "Admin access required"
            }), 403

        return f(*args, **kwargs)

    return decorated_function
