from functools import wraps
from flask import jsonify
from flask_login import current_user


# -------------------------------
# API Login Required
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


# =========================================================
# 🔥 COMPATIBILITY LAYER (IMPORTANT)
# =========================================================

# These fix your import errors without changing routes


def login_required(f):
    """
    Alias for login_required_api (for backward compatibility)
    """
    return login_required_api(f)


def admin_required(f):
    """
    Alias for admin_required_api (for backward compatibility)
    """
    return admin_required_api(f)
