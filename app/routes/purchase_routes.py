from flask import request, jsonify, session
from app.services.package_service import purchase_package
from app.utils.auth import login_required
from flask import Blueprint

main = Blueprint("main", __name__)


@main.route("/purchase-package", methods=["POST"])
@login_required
def purchase_package_api():

    user_id = session["user_id"]

    data = request.json
    package_id = data.get("package_id")

    if not package_id:
        return jsonify({
            "success": False,
            "message": "Package ID required"
        }), 400

    result = purchase_package(user_id, package_id)

    return jsonify(result)
