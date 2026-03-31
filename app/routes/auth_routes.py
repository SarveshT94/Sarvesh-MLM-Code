from flask import request, jsonify, session
from app.services.auth_service import login_user
from app.routes.main_routes import main


@main.route("/api/auth/login", methods=["POST"])
def login():

    data = request.json

    result = login_user(
        data["email"],
        data["password"]
    )

    if not result["success"]:
        return jsonify(result), 400

    session["user_id"] = result["user"]["id"]

    return jsonify({
        "success": True,
        "user": result["user"],        
        "token": result.get("token")
    })
