"""
app/routes/admin/store_routes.py  —  ADMIN STORE (pages + JSON API)

Pages (Bootstrap admin, extends admin/base.html)
  GET  /admin/store                    dashboard + settings
  GET  /admin/store/products           product list (+ filters)
  GET  /admin/store/products/new
  GET  /admin/store/products/<id>      edit product / variants / images
  GET  /admin/store/orders             order management
  GET  /admin/store/orders/<id>
JSON
  POST /admin/store/settings
  POST /admin/store/categories             (create/update)
  POST /admin/store/products               (create/update)
  POST /admin/store/products/<id>/delete
  POST /admin/store/products/<id>/variants (create/update)
  POST /admin/store/products/<id>/variants/<vid>/delete
  POST /admin/store/products/<id>/images   (multipart upload)
  POST /admin/store/images/<img_id>/delete
  POST /admin/store/orders/<id>/status     {status, courier, tracking_no, note}
  POST /admin/store/orders/<id>/cancel
  POST /admin/store/orders/<id>/mark-paid
"""
from __future__ import annotations

import os
import uuid
import logging

from flask import Blueprint, render_template, request, jsonify, redirect, flash, abort, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.services import store_service as svc

logger = logging.getLogger(__name__)
admin_store_bp = Blueprint("admin_store", __name__)

UPLOAD_DIR = "app/static/uploads/products"
ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}


def _admin():
    if not current_user.is_authenticated or getattr(current_user, "role_id", 2) != 1:
        abort(403)


def _json_or_form():
    return request.get_json(silent=True) or request.form.to_dict()


def _ok(**kw):
    return jsonify({"success": True, **kw})


def _err(msg, code=400):
    return jsonify({"success": False, "message": str(msg)}), code


# =============================================================== pages
@admin_store_bp.route("/admin/store")
def store_home():
    _admin()
    return render_template("admin/store_dashboard.html",
                           stats=svc.store_dashboard_stats(),
                           settings=svc.get_store_settings(),
                           categories=svc.list_categories(include_inactive=True))


@admin_store_bp.route("/admin/store/products")
def store_products():
    _admin()
    a = request.args
    data = svc.list_products(category=a.get("category"), q=a.get("q"), page=a.get("page", 1),
                             page_size=30, sort=a.get("sort", "newest"), include_inactive=True)
    return render_template("admin/store_products.html", data=data,
                           categories=svc.list_categories(include_inactive=True), args=a)


@admin_store_bp.route("/admin/store/products/new")
def store_product_new():
    _admin()
    return render_template("admin/store_product_edit.html", product=None,
                           categories=svc.list_categories(include_inactive=True))


@admin_store_bp.route("/admin/store/products/<int:pid>")
def store_product_edit(pid):
    _admin()
    p = svc.get_product(pid, include_inactive=True)
    if not p:
        flash("Product not found", "danger")
        return redirect("/admin/store/products")
    return render_template("admin/store_product_edit.html", product=p,
                           categories=svc.list_categories(include_inactive=True))


@admin_store_bp.route("/admin/store/orders")
def store_orders():
    _admin()
    a = request.args
    data = svc.admin_list_orders(status=a.get("status") or None, payment_status=a.get("payment") or None,
                                 q=a.get("q"), page=a.get("page", 1))
    return render_template("admin/store_orders.html", data=data, args=a, flow=svc.ORDER_FLOW)


@admin_store_bp.route("/admin/store/orders/<int:oid>")
def store_order_detail(oid):
    _admin()
    o = svc.get_order(None, oid, admin=True)
    if not o:
        flash("Order not found", "danger")
        return redirect("/admin/store/orders")
    return render_template("admin/store_order_detail.html", o=o, flow=svc.ORDER_FLOW)


# =============================================================== settings / categories
@admin_store_bp.route("/admin/store/settings", methods=["POST"])
def store_settings_save():
    _admin()
    d = _json_or_form()
    allowed = {"activation_match_mode", "shipping_fee", "free_shipping_above",
               "prices_include_gst", "store_name", "min_repurchase_amount"}
    vals = {k: v for k, v in d.items() if k in allowed}
    if vals.get("activation_match_mode") not in (None, "exact", "floor"):
        return _err("activation_match_mode must be exact or floor")
    svc.update_store_settings(vals)
    if request.is_json:
        return _ok()
    flash("Store settings saved", "success")
    return redirect("/admin/store")


@admin_store_bp.route("/admin/store/categories", methods=["POST"])
def category_save():
    _admin()
    d = _json_or_form()
    if not (d.get("name") or "").strip():
        return _err("Name required")
    d["is_active"] = str(d.get("is_active", "true")).lower() in ("1", "true", "on", "yes")
    cid = svc.admin_save_category(d, d.get("id") or None)
    if request.is_json:
        return _ok(id=cid)
    flash("Category saved", "success")
    return redirect("/admin/store")


# =============================================================== products
@admin_store_bp.route("/admin/store/products", methods=["POST"])
def product_save():
    _admin()
    d = _json_or_form()
    try:
        if not (d.get("name") or "").strip() or not d.get("category_id"):
            return _err("Name and category are required")
        d["is_active"] = str(d.get("is_active", "true")).lower() in ("1", "true", "on", "yes")
        d["is_featured"] = str(d.get("is_featured", "false")).lower() in ("1", "true", "on", "yes")
        pid = svc.admin_save_product(d, d.get("id") or None)
        if request.is_json:
            return _ok(id=pid)
        flash("Product saved", "success")
        return redirect(f"/admin/store/products/{pid}")
    except Exception as e:
        logger.error("product save failed: %s", e, exc_info=True)
        return _err(e)


@admin_store_bp.route("/admin/store/products/<int:pid>/delete", methods=["POST"])
def product_delete(pid):
    _admin()
    how = svc.admin_delete_product(pid)
    if request.is_json:
        return _ok(result=how)
    flash("Product archived (it has order history)" if how == "archived" else "Product deleted", "success")
    return redirect("/admin/store/products")


@admin_store_bp.route("/admin/store/products/<int:pid>/variants", methods=["POST"])
def variant_save(pid):
    _admin()
    d = _json_or_form()
    try:
        d["is_active"] = str(d.get("is_active", "true")).lower() in ("1", "true", "on", "yes")
        vid = svc.admin_save_variant(pid, d, d.get("id") or None)
        if request.is_json:
            return _ok(id=vid)
        flash("Variant saved", "success")
    except ValueError as e:
        if request.is_json:
            return _err(e)
        flash(str(e), "danger")
    return redirect(f"/admin/store/products/{pid}")


@admin_store_bp.route("/admin/store/products/<int:pid>/variants/<int:vid>/delete", methods=["POST"])
def variant_delete(pid, vid):
    _admin()
    how = svc.admin_delete_variant(pid, vid)
    if request.is_json:
        return _ok(result=how)
    flash("Variant archived" if how == "archived" else "Variant deleted", "success")
    return redirect(f"/admin/store/products/{pid}")


@admin_store_bp.route("/admin/store/products/<int:pid>/images", methods=["POST"])
def image_upload(pid):
    _admin()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    files = request.files.getlist("images") or ([request.files["image"]] if "image" in request.files else [])
    variant_id = request.form.get("variant_id") or None
    saved = 0
    for f in files:
        if not f or not f.filename:
            continue
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED:
            continue
        name = f"{pid}_{uuid.uuid4().hex[:10]}.{ext}"
        f.save(os.path.join(UPLOAD_DIR, secure_filename(name)))
        svc.admin_add_image(pid, f"/static/uploads/products/{name}", variant_id)
        saved += 1
    if request.is_json or request.headers.get("X-Requested-With") == "fetch":
        return _ok(saved=saved)
    flash(f"{saved} image(s) uploaded" if saved else "No valid image uploaded", "success" if saved else "warning")
    return redirect(f"/admin/store/products/{pid}")


@admin_store_bp.route("/admin/store/images/<int:img_id>/delete", methods=["POST"])
def image_delete(img_id):
    _admin()
    url = svc.admin_delete_image(img_id)
    if url and url.startswith("/static/uploads/products/"):
        try:
            os.remove(os.path.join("app", url.lstrip("/")))
        except OSError:
            pass
    if request.is_json:
        return _ok()
    return redirect(request.referrer or "/admin/store/products")


# =============================================================== orders
@admin_store_bp.route("/admin/store/orders/<int:oid>/status", methods=["POST"])
def order_status(oid):
    _admin()
    d = _json_or_form()
    try:
        svc.admin_update_order_status(oid, d.get("status"), current_user.id, d.get("courier"),
                                      d.get("tracking_no"), d.get("note"))
        if request.is_json:
            return _ok()
        flash(f"Order marked {d.get('status')}", "success")
    except ValueError as e:
        if request.is_json:
            return _err(e)
        flash(str(e), "danger")
    return redirect(f"/admin/store/orders/{oid}")


@admin_store_bp.route("/admin/store/orders/<int:oid>/cancel", methods=["POST"])
def order_cancel(oid):
    _admin()
    d = _json_or_form()
    try:
        r = svc.cancel_order(None, oid, d.get("reason") or "Cancelled by admin", admin_id=current_user.id)
        if request.is_json:
            return _ok(**r)
        msg = f"Order cancelled. Refunded ₹{r['refunded']:.2f} to wallet."
        if r.get("refund_pending"):
            msg += f" ₹{r['refund_pending']:.2f} must be refunded at the payment gateway by you."
        flash(msg, "warning")
    except ValueError as e:
        if request.is_json:
            return _err(e)
        flash(str(e), "danger")
    return redirect(f"/admin/store/orders/{oid}")


@admin_store_bp.route("/admin/store/orders/<int:oid>/mark-paid", methods=["POST"])
def order_mark_paid(oid):
    _admin()
    d = _json_or_form()
    try:
        svc.admin_mark_paid(oid, current_user.id, d.get("note"))
        if request.is_json:
            return _ok()
        flash("Payment recorded — plan benefits & commissions applied.", "success")
    except ValueError as e:
        if request.is_json:
            return _err(e)
        flash(str(e), "danger")
    return redirect(f"/admin/store/orders/{oid}")
