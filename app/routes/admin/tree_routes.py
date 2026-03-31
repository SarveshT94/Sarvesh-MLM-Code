from flask import Blueprint, jsonify
from app.services.admin.tree_service import get_user_tree
from app.utils.auth import admin_required

admin_tree_bp = Blueprint("admin_tree", __name__)

@admin_tree_bp.route("/admin/tree/<int:user_id>", methods=["GET"])
@admin_required
def admin_view_tree(user_id):

    tree = get_user_tree(user_id)

    return jsonify({
        "success": True,
        "tree": tree
    })
