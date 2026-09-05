import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, flash, current_app
from app.db import get_cursor
from app.services.package_service import (
    get_all_plans,
    update_plan,
    create_plan,
    add_plan_image,
    get_global_commissions,
    update_global_commission,
    get_level_commissions
)

admin_package_bp = Blueprint("admin_package", __name__)

# Ensure the upload directory exists
UPLOAD_FOLDER = 'app/static/uploads/packages'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@admin_package_bp.route("/admin/packages", methods=["GET"])
def manage_packages():
    """
    Loads the complete business configuration dashboard.
    """
    try:
        backend_url = request.host_url.rstrip('/')

        with get_cursor() as cur:

            cur.execute("""
                SELECT *
                FROM subscription_plans
                ORDER BY price ASC
            """)

            raw_plans = cur.fetchall()

            packages = []

            for plan in raw_plans:

                pkg = dict(plan)

                # Fetch gallery images
                cur.execute("""
                    SELECT id, image_path
                    FROM plan_images
                    WHERE plan_id = %s
                    ORDER BY id ASC
                """, (pkg['id'],))

                images = []

                for row in cur.fetchall():

                    path = row['image_path']

                    if path and path.startswith('/'):
                        path = f"{backend_url}{path}"

                    images.append({
                        'id': row['id'],
                        'path': path
                    })

                # Fallback old image_url
                if not images and pkg.get('image_url'):

                    path = pkg['image_url']

                    if path and path.startswith('/'):
                        path = f"{backend_url}{path}"

                    images = [{
                        'id': 0,
                        'path': path
                    }]

                pkg['images'] = images

                packages.append(pkg)

        # Load dynamic settings
        settings = get_global_commissions()
        level_comms = get_level_commissions()

    except Exception as e:

        packages = []
        settings = []
        level_comms = []

        print(f"Error fetching business config: {e}")

    return render_template(
        "admin/packages.html",
        packages=packages,
        settings=settings,
        level_comms=level_comms
    )


@admin_package_bp.route("/admin/packages/add", methods=["POST"])
def admin_add_plan():
    """
    Creates a new combo plan.
    """
    try:

        name = request.form.get("name")
        price = request.form.get("price")
        coupons = request.form.get("coupons", 12)
        
        # ✅ NEW: Capture product_cost from form (default to 0 if left blank)
        product_cost = request.form.get("product_cost") or 0

        if name and price:

            create_plan(name, price, coupons, product_cost)

            flash(
                "New plan created! Click 'Edit' to upload product images.",
                "success"
            )

    except Exception as e:

        flash(
            f"Error creating plan: {str(e)}",
            "danger"
        )

    return redirect("/admin/packages")


@admin_package_bp.route("/admin/packages/update", methods=["POST"])
def admin_update_plan():
    """
    Updates a plan and uploads multiple images.
    """
    try:

        plan_id = request.form.get("plan_id")
        price = request.form.get("price")
        coupons = request.form.get("coupons")
        
        # ✅ NEW: Capture product_cost from form for updates
        product_cost = request.form.get("product_cost") or 0

        is_active = (
            True
            if request.form.get("is_active") == "on"
            else False
        )

        # Update basic info (Now includes product_cost)
        update_plan(
            plan_id,
            price,
            coupons,
            is_active,
            product_cost
        )

        # Handle gallery upload
        files = request.files.getlist('product_images')

        for file in files:

            if file and file.filename != '':

                filename = secure_filename(file.filename)

                unique_filename = f"plan_{plan_id}_{filename}"

                filepath = os.path.join(
                    UPLOAD_FOLDER,
                    unique_filename
                )

                # Save physical file
                file.save(filepath)

                # Save DB path
                web_path = f"/static/uploads/packages/{unique_filename}"

                add_plan_image(
                    plan_id,
                    web_path
                )

        flash(
            "Package & Images updated successfully!",
            "success"
        )

    except Exception as e:

        flash(
            f"Error updating package: {str(e)}",
            "danger"
        )

    return redirect("/admin/packages")


@admin_package_bp.route(
    "/admin/packages/delete-image/<int:image_id>",
    methods=["POST"]
)
def admin_delete_package_image(image_id):
    """
    Deletes package image from DB and storage.
    """

    try:

        with get_cursor() as cur:

            cur.execute("""
                SELECT image_path, plan_id
                FROM plan_images
                WHERE id = %s
            """, (image_id,))

            img_data = cur.fetchone()

            if img_data:

                # Delete DB record
                cur.execute("""
                    DELETE FROM plan_images
                    WHERE id = %s
                """, (image_id,))

                # Update fallback image_url
                cur.execute("""
                    SELECT image_path
                    FROM plan_images
                    WHERE plan_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                """, (img_data['plan_id'],))

                next_img = cur.fetchone()

                new_url = (
                    next_img['image_path']
                    if next_img
                    else None
                )

                cur.execute("""
                    UPDATE subscription_plans
                    SET image_url = %s
                    WHERE id = %s
                """, (
                    new_url,
                    img_data['plan_id']
                ))

                # Delete physical file
                try:

                    path_string = img_data['image_path']

                    if (
                        path_string
                        and path_string.startswith('/static/')
                    ):

                        safe_path = path_string.replace(
                            '/static/',
                            ''
                        )

                        filepath = os.path.join(
                            current_app.static_folder,
                            safe_path
                        )

                        if os.path.exists(filepath):
                            os.remove(filepath)

                except Exception as e:
                    print(
                        f"Could not delete physical file: {str(e)}"
                    )

        flash(
            "Image deleted successfully.",
            "success"
        )

    except Exception as e:

        print(f"Error deleting image: {str(e)}")

        flash(
            "Error deleting image.",
            "danger"
        )

    return redirect("/admin/packages")


# =========================================================
# GLOBAL COMMISSION UPDATE
# =========================================================
@admin_package_bp.route(
    "/admin/commissions/update",
    methods=["POST"]
)
def admin_update_commission():

    try:

        setting_key = request.form.get("setting_key")

        percentage_value = request.form.get(
            "percentage_value"
        )

        update_global_commission(
            setting_key,
            percentage_value
        )

        flash(
            f"{setting_key.replace('_', ' ').title()} updated successfully!",
            "success"
        )

    except Exception as e:

        flash(
            f"Error updating commission: {str(e)}",
            "danger"
        )

    return redirect("/admin/packages")


# =========================================================
# LEVEL COMMISSION UPDATE
# =========================================================
@admin_package_bp.route(
    "/admin/level-commissions/update",
    methods=["POST"]
)
def admin_update_level_commission():

    try:

        level = request.form.get("level")

        percentage_value = request.form.get(
            "percentage_value"
        )

        with get_cursor() as cur:

            cur.execute("""
                UPDATE level_commissions
                SET commission_percentage = %s
                WHERE level = %s
            """, (
                percentage_value,
                level
            ))

        flash(
            f"Level {level} commission updated to {percentage_value}%!",
            "success"
        )

    except Exception as e:

        flash(
            f"Error updating level commission: {str(e)}",
            "danger"
        )

    return redirect("/admin/packages")
