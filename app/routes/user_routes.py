from app.services.income_service import get_income_summary
from app.services.rank_service import get_user_rank

@main.route("/redeem-epin", methods=["POST"])
@login_required
def redeem_epin_api():

    data = request.json
    user_id = session["user_id"]

    pin_code = data.get("pin_code")

    result = redeem_epin(user_id, pin_code)

    return jsonify(result)


# -----------------------------
# INCOME DASHBOARD API
# -----------------------------

@main.route("/dashboard-income", methods=["GET"])
@login_required
def dashboard_income():

    user_id = session["user_id"]

    result = get_income_summary(user_id)

    return jsonify(result)


# -----------------------------
# RANK DASHBOARD API
# -----------------------------

@main.route("/my-rank", methods=["GET"])
@login_required
def my_rank():

    user_id = session["user_id"]

    rank = get_user_rank(user_id)

    return jsonify(rank)
