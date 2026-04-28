import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, flash, current_app
from app.db import get_cursor
from app.services.package_service import (
    get_all_plans, update_plan, create_plan, add_plan_image,
    get_global_commissions, update_global_commission,
    get_level_commissions, get_team_target_bonuses
)

admin_package_bp = Blueprint("admin_package", __name__)

# Ensure the upload directory exists
UPLOAD_FOLDER = 'app/static/uploads/packages'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@admin_package_bp.route("/admin/packages", methods=["GET"])
def manage_packages():
    """Loads the complete business configuration dashboard."""
    try:
        # Get the host URL to make local images visible
        backend_url = request.host_url.rstrip('/')
        
        with get_cursor() as cur:
            cur.execute("SELECT * FROM subscription_plans ORDER BY price ASC")
            raw_plans = cur.fetchall()
            
            packages = []
            for plan in raw_plans:
                pkg = dict(plan)
                
                # Fetch ID and Path for the new gallery array format
                cur.execute("SELECT id, image_path FROM plan_images WHERE plan_id = %s ORDER BY id ASC", (pkg['id'],))
                images = []
                for row in cur.fetchall():
                    path = row['image_path']
                    if path and path.startswith('/'):
                        path = f"{backend_url}{path}"
                    images.append({'id': row['id'], 'path': path})
                
                # Fallback to old string if the gallery is empty
                if not images and pkg.get('image_url'):
                    path = pkg['image_url']
                    if path and path.startswith('/'):
                        path = f"{backend_url}{path}"
                    images = [{'id': 0, 'path': path}]
                    
                pkg['images'] = images
                packages.append(pkg)
                
        # Fetch the rest of the settings
        settings = get_global_commissions()
        level_comms = get_level_commissions()
        target_bonuses = get_team_target_bonuses()
        
    except Exception as e:
        packages, settings, level_comms, target_bonuses = [], [], [], []
        print(f"Error fetching business config: {e}")

    return render_template(
        "admin/packages.html", 
        packages=packages, 
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
            flash("New plan created! Click 'Edit' to upload product images.", "success")
            
    except Exception as e:
        flash(f"Error creating plan: {str(e)}", "danger")
    return redirect("/admin/packages")


@admin_package_bp.route("/admin/packages/update", methods=["POST"])
def admin_update_plan():
    """Updates a plan AND securely saves multiple uploaded images from the local gallery."""
    try:
        plan_id = request.form.get("plan_id")
        price = request.form.get("price")
        coupons = request.form.get("coupons")
        is_active = True if request.form.get("is_active") == "on" else False 
        
        # 1. Update basic text info
        update_plan(plan_id, price, coupons, is_active)
        
        # 2. Handle Multiple File Uploads
        files = request.files.getlist('product_images')
        
        for file in files:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_filename = f"plan_{plan_id}_{filename}"
                filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                # Save the physical file to the server
                file.save(filepath)
                
                # Save the web path to the database
                web_path = f"/static/uploads/packages/{unique_filename}"
                add_plan_image(plan_id, web_path)

        flash("Package & Images updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating package: {str(e)}", "danger")
    return redirect("/admin/packages")


@admin_package_bp.route("/admin/packages/delete-image/<int:image_id>", methods=["POST"])
def admin_delete_package_image(image_id):
    """Deletes an image from the database and the server hard drive."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT image_path, plan_id FROM plan_images WHERE id = %s", (image_id,))
            img_data = cur.fetchone()
            
            if img_data:
                # Delete from DB
                cur.execute("DELETE FROM plan_images WHERE id = %s", (image_id,))
                
                # Update fallback URL
                cur.execute("SELECT image_path FROM plan_images WHERE plan_id = %s ORDER BY id DESC LIMIT 1", (img_data['plan_id'],))
                next_img = cur.fetchone()
                new_url = next_img['image_path'] if next_img else None
                cur.execute("UPDATE subscription_plans SET image_url = %s WHERE id = %s", (new_url, img_data['plan_id']))
                
                # Physically delete the file
                try:
                    path_string = img_data['image_path']
                    if path_string and path_string.startswith('/static/'):
                        safe_path = path_string.replace('/static/', '')
                        filepath = os.path.join(current_app.static_folder, safe_path)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                except Exception as e:
                    print(f"Could not delete physical file: {str(e)}")
                    
        flash("Image deleted successfully.", "success")
    except Exception as e:
        print(f"Error deleting image: {str(e)}")
        flash("Error deleting image.", "danger")
        
    return redirect("/admin/packages")


# --- Commission Updates ---
@admin_package_bp.route("/admin/commissions/update", methods=["POST"])
def admin_update_commission():
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
    try:
        target_id = request.form.get("target_id")
        bonus_percentage = request.form.get("bonus_percentage")
        with get_cursor() as cur:
            cur.execute("UPDATE team_target_bonuses SET bonus_percentage = %s WHERE id = %s", (bonus_percentage, target_id))
        flash("Team Target Bonus updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating target bonus: {str(e)}", "danger")
    return redirect("/admin/packages")
