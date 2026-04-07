from functools import wraps
from flask import jsonify
from flask_login import current_user


# -------------------------------
# API Login Required (Flask-Login based)
# -------------------------------
def login_required_api(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not current_user.is_authenticated:
            return jsonify({
                "status": "error",
                "message": "Login required"
            }), 401

        return f(*args, **kwargs)

    return decorated_function


# -------------------------------
# Admin Required (API)
# -------------------------------
def admin_required_api(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not current_user.is_authenticated:
            return jsonify({
                "status": "error",
                "message": "Login required"
            }), 401

        # role_id = 1 → admin
        if getattr(current_user, "role_id", None) != 1:
            return jsonify({
                "status": "error",
                "message": "Admin access required"
            }), 403

        return f(*args, **kwargs)

    return decorated_function
