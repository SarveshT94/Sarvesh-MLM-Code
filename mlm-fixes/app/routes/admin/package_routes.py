"""
app/routes/admin/package_routes.py  —  COMPLETE REPLACEMENT

Admin screen for Packages + the Commission/Business plan.

Important fix vs the old file:
  * Level percentages are now saved to the CANONICAL `commission_plan` table
    (which the commission engine actually reads) and mirrored to the legacy
    `level_commissions` table so old screens keep working.
  * Saving busts the Redis config cache so new % apply immediately.
  * Every route is admin-protected.
"""
import os
from decimal import Decimal, InvalidOperation

from werkzeug.utils import secure_filename
from flask import (
    Blueprint, render_template, request, redirect, flash, current_app, abort
)
from flask_login import login_required, current_user

from app.db import get_cursor
from app.cache import cache
from app.services.package_service import (
    get_all_plans,
    update_plan,
    create_plan,
    add_plan_image,
    get_global_commissions,
    update_global_commission,
    get_level_commissions,
)

admin_package_bp = Blueprint("admin_package", __name__)

UPLOAD_FOLDER = "app/static/uploads/packages"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _admin_only():
    """All package/commission routes are admin-only."""
    if not current_user.is_authenticated or getattr(current_user, "role_id", 2) != 1:
        abort(403)


def _to_decimal(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, ValueError):
        return Decimal(default)


# ===========================================================================
# PAGE
# ===========================================================================
@admin_package_bp.route("/admin/packages", methods=["GET"])
@login_required
def manage_packages():
    _admin_only()
    try:
        backend_url = request.host_url.rstrip("/")
        packages = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM subscription_plans ORDER BY price ASC")
            for plan in cur.fetchall():
                pkg = dict(plan)
                cur.execute(
                    "SELECT id, image_path FROM plan_images WHERE plan_id = %s ORDER BY id ASC",
                    (pkg["id"],),
                )
                images = []
                for row in cur.fetchall():
                    path = row["image_path"]
                    if path and path.startswith("/"):
                        path = f"{backend_url}{path}"
                    images.append({"id": row["id"], "path": path})
                if not images and pkg.get("image_url"):
                    p = pkg["image_url"]
                    if p.startswith("/"):
                        p = f"{backend_url}{p}"
                    images = [{"id": 0, "path": p}]
                pkg["images"] = images
                packages.append(pkg)

            cur.execute(
                "SELECT level, rank_name, req_team_size, req_business_vol, bonus_percentage "
                "FROM rank_rules ORDER BY level ASC"
            )
            ranks = [dict(r) for r in cur.fetchall()]

        settings = get_global_commissions()
        level_comms = get_level_commissions()
    except Exception as e:
        current_app.logger.error("manage_packages error: %s", e)
        packages, settings, level_comms, ranks = [], [], [], []

    return render_template(
        "admin/packages.html",
        packages=packages,
        settings=settings,
        level_comms=level_comms,
        ranks=ranks,
    )


# ===========================================================================
# PLANS
# ===========================================================================
@admin_package_bp.route("/admin/packages/add", methods=["POST"])
@login_required
def admin_add_plan():
    _admin_only()
    try:
        name = (request.form.get("name") or "").strip()
        price = _to_decimal(request.form.get("price"))
        coupons = int(request.form.get("coupons") or 12)
        product_cost = _to_decimal(request.form.get("product_cost"))
        if not name or price <= 0:
            flash("Plan name and a valid price are required.", "danger")
        else:
            new_id = create_plan(name, price, coupons, product_cost)
            # Attach uploaded product image to the newly created plan.
            for file in request.files.getlist("product_images"):
                if file and file.filename:
                    fname = secure_filename(file.filename)
                    unique = f"plan_{new_id}_{fname}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique))
                    add_plan_image(new_id, f"/static/uploads/packages/{unique}")
            flash("New product created!", "success")
    except Exception as e:
        flash(f"Error creating plan: {e}", "danger")
    return redirect("/admin/packages")


@admin_package_bp.route("/admin/packages/update", methods=["POST"])
@login_required
def admin_update_plan():
    _admin_only()
    try:
        plan_id = request.form.get("plan_id")
        price = _to_decimal(request.form.get("price"))
        coupons = int(request.form.get("coupons") or 12)
        product_cost = _to_decimal(request.form.get("product_cost"))
        is_active = request.form.get("is_active") == "on"

        update_plan(plan_id, price, coupons, is_active, product_cost)

        for file in request.files.getlist("product_images"):
            if file and file.filename:
                filename = secure_filename(file.filename)
                unique = f"plan_{plan_id}_{filename}"
                file.save(os.path.join(UPLOAD_FOLDER, unique))
                add_plan_image(plan_id, f"/static/uploads/packages/{unique}")

        flash("Package updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating package: {e}", "danger")
    return redirect("/admin/packages")


@admin_package_bp.route("/admin/packages/delete-image/<int:image_id>", methods=["POST"])
@login_required
def admin_delete_package_image(image_id):
    _admin_only()
    try:
        with get_cursor() as cur:
            cur.execute("SELECT image_path, plan_id FROM plan_images WHERE id = %s", (image_id,))
            img = cur.fetchone()
            if img:
                cur.execute("DELETE FROM plan_images WHERE id = %s", (image_id,))
                cur.execute(
                    "SELECT image_path FROM plan_images WHERE plan_id = %s ORDER BY id DESC LIMIT 1",
                    (img["plan_id"],),
                )
                nxt = cur.fetchone()
                cur.execute(
                    "UPDATE subscription_plans SET image_url = %s WHERE id = %s",
                    (nxt["image_path"] if nxt else None, img["plan_id"]),
                )
                try:
                    p = img["image_path"]
                    if p and p.startswith("/static/"):
                        fp = os.path.join(current_app.static_folder, p.replace("/static/", "", 1))
                        if os.path.exists(fp):
                            os.remove(fp)
                except Exception:
                    pass
        flash("Image deleted.", "success")
    except Exception as e:
        flash(f"Error deleting image: {e}", "danger")
    return redirect("/admin/packages")


# ===========================================================================
# GLOBAL COMMISSIONS (direct %, cashback, TDS, admin fee ...)
# ===========================================================================
@admin_package_bp.route("/admin/commissions/update", methods=["POST"])
@login_required
def admin_update_commission():
    _admin_only()
    try:
        key = request.form.get("setting_key")
        value = _to_decimal(request.form.get("percentage_value"))
        if not key:
            flash("Missing setting key.", "danger")
        else:
            with get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO global_commissions (setting_key, percentage_value, description)
                    VALUES (%s, %s, '')
                    ON CONFLICT (setting_key) DO UPDATE SET percentage_value = EXCLUDED.percentage_value
                    """,
                    (key, value),
                )
            cache.delete("commissions:config")
            flash(f"{key.replace('_', ' ').title()} updated to {value}%.", "success")
    except Exception as e:
        flash(f"Error updating commission: {e}", "danger")
    return redirect("/admin/packages")


# ===========================================================================
# LEVEL COMMISSIONS  (the 1..10 generation ladder)
# Saved into BOTH commission_plan (canonical, used by the engine) and the
# legacy level_commissions table.
# ===========================================================================
@admin_package_bp.route("/admin/level-commissions/update", methods=["POST"])
@login_required
def admin_update_level_commission():
    _admin_only()
    try:
        level = int(request.form.get("level"))
        value = _to_decimal(request.form.get("percentage_value"))
        if level < 1 or value < 0:
            flash("Invalid level or percentage.", "danger")
        else:
            with get_cursor() as cur:
                # Canonical table the engine reads first.
                cur.execute(
                    """
                    INSERT INTO commission_plan (level, percentage, is_active)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (level) DO UPDATE SET percentage = EXCLUDED.percentage,
                                                     is_active = TRUE
                    """,
                    (level, value),
                )
                # Mirror to legacy table (same column the old template used).
                cur.execute(
                    """
                    INSERT INTO level_commissions (level, commission_percentage)
                    VALUES (%s, %s)
                    ON CONFLICT (level) DO UPDATE SET commission_percentage = EXCLUDED.commission_percentage
                    """,
                    (level, value),
                )
            cache.delete("commissions:config")
            flash(f"Level {level} commission updated to {value}%.", "success")
    except Exception as e:
        flash(f"Error updating level commission: {e}", "danger")
    return redirect("/admin/packages")
