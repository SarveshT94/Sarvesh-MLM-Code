from flask import Blueprint, render_template, request, redirect, flash
from app.db import get_cursor
from app.services.package_service import (
    get_all_plans, update_plan, create_plan,
    get_global_commissions, update_global_commission,
    get_level_commissions, get_team_target_bonuses
)

admin_package_bp = Blueprint("admin_package", __name__)

@admin_package_bp.route("/admin/packages", methods=["GET"])
def manage_packages():
    """Loads the complete business configuration dashboard."""
    try:
        plans = get_all_plans()
        settings = get_global_commissions()
        level_comms = get_level_commissions()
        target_bonuses = get_team_target_bonuses()
    except Exception as e:
        plans, settings, level_comms, target_bonuses = [], [], [], []
        print(f"Error fetching business config: {e}")

    return render_template(
        "admin/manage_packages.html", 
        plans=plans, 
        settings=settings, 
        level_comms=level_comms,
        target_bonuses=target_bonuses
    )

@admin_package_bp.route("/admin/packages/add", methods=["POST"])
def admin_add_plan():
    """Creates a new combo plan."""
    try:
        name = request.form.get("name")
        price = request.form.get("price")
        coupons = request.form.get("coupons", 12)
        
        if name and price:
            create_plan(name, price, coupons)
            flash("New plan created successfully!", "success")
    except Exception as e:
        flash(f"Error creating plan: {str(e)}", "danger")
    return redirect("/admin/packages")

@admin_package_bp.route("/admin/packages/update", methods=["POST"])
def admin_update_plan():
    """Updates a specific subscription plan."""
    try:
        plan_id = request.form.get("plan_id")
        price = request.form.get("price")
        coupons = request.form.get("coupons")
        is_active = True if request.form.get("is_active") == "on" else False 
        
        update_plan(plan_id, price, coupons, is_active)
        flash("Package updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating package: {str(e)}", "danger")
    return redirect("/admin/packages")

@admin_package_bp.route("/admin/commissions/update", methods=["POST"])
def admin_update_commission():
    """Updates global flat-rate commissions."""
    try:
        setting_key = request.form.get("setting_key")
        percentage_value = request.form.get("percentage_value")
        
        update_global_commission(setting_key, percentage_value)
        flash(f"{setting_key.replace('_', ' ').title()} updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating commission: {str(e)}", "danger")
    return redirect("/admin/packages")

@admin_package_bp.route("/admin/level-commissions/update", methods=["POST"])
def admin_update_level_commission():
    """Updates a specific level's percentage."""
    try:
        level = request.form.get("level")
        percentage_value = request.form.get("percentage_value")
        with get_cursor() as cur:
            cur.execute("UPDATE level_commissions SET commission_percentage = %s WHERE level = %s", (percentage_value, level))
        flash(f"Level {level} commission updated to {percentage_value}%!", "success")
    except Exception as e:
        flash(f"Error updating level commission: {str(e)}", "danger")
    return redirect("/admin/packages")

@admin_package_bp.route("/admin/target-bonuses/update", methods=["POST"])
def admin_update_target_bonus():
    """Updates team target bonus percentages."""
    try:
        target_id = request.form.get("target_id")
        bonus_percentage = request.form.get("bonus_percentage")
        with get_cursor() as cur:
            cur.execute("UPDATE team_target_bonuses SET bonus_percentage = %s WHERE id = %s", (bonus_percentage, target_id))
        flash("Team Target Bonus updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating target bonus: {str(e)}", "danger")
    return redirect("/admin/packages")
