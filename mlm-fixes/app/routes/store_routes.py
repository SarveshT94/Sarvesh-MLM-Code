"""
app/routes/store_routes.py  —  STORE API (member facing)   prefix: /api/store

Public
  GET  /categories
  GET  /products?category=&q=&page=&sort=&min_price=&max_price=&featured=1
  GET  /products/<id_or_slug>
  GET  /plans                         plan tiers + what the member currently has
Member (login)
  GET  /cart                          cart + plan_match (activation/upgrade/repurchase)
  POST /cart/add        {variant_id, qty}
  POST /cart/update     {variant_id, qty}   (qty 0 removes)
  POST /cart/clear
  GET  /addresses  | POST /addresses | POST /addresses/<id>/delete
  POST /checkout       {address_id, payment_method: wallet|online|split, wallet_amount?, note?}
  POST /payment/verify {gateway_order_id, gateway_payment_id, signature?}
  GET  /orders | GET /orders/<id> | POST /orders/<id>/cancel
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user

from app.utils.auth import login_required
from app.services import store_service as svc

logger = logging.getLogger(__name__)
store_bp = Blueprint("store", __name__)


def _err(msg, code=400):
    return jsonify({"success": False, "message": str(msg)}), code


# ---------------------------------------------------------------- catalog
@store_bp.route("/categories")
def categories():
    return jsonify({"success": True, "data": svc.list_categories()})


@store_bp.route("/products")
def products():
    a = request.args
    try:
        data = svc.list_products(
            category=a.get("category"), q=a.get("q"), page=a.get("page", 1),
            page_size=a.get("page_size", 24), sort=a.get("sort", "newest"),
            min_price=a.get("min_price") or None, max_price=a.get("max_price") or None,
            featured=a.get("featured") in ("1", "true"),
        )
        return jsonify({"success": True, **data})
    except Exception as e:
        logger.error("products list failed: %s", e, exc_info=True)
        return _err("Failed to load products", 500)


@store_bp.route("/products/<key>")
def product(key):
    p = svc.get_product(key)
    if not p:
        return _err("Product not found", 404)
    return jsonify({"success": True, "data": p})


@store_bp.route("/plans")
def plans():
    from app.db import get_cursor
    with get_cursor() as cur:
        match = svc.evaluate_plan_match(cur, current_user.id if current_user.is_authenticated else None, 0) \
            if current_user.is_authenticated else None
        cur.execute("SELECT id, name, price, lucky_draw_coupons FROM subscription_plans WHERE is_active ORDER BY price")
        tiers = [dict(r) for r in cur.fetchall()]
    for t in tiers:
        t["price"] = float(t["price"])
    return jsonify({"success": True, "tiers": tiers, "member": match})


# ---------------------------------------------------------------- cart
@store_bp.route("/cart")
@login_required
def cart():
    return jsonify({"success": True, "data": svc.get_cart(current_user.id)})


@store_bp.route("/cart/add", methods=["POST"])
@login_required
def cart_add():
    d = request.get_json(silent=True) or {}
    try:
        return jsonify({"success": True, "data": svc.add_to_cart(current_user.id, int(d.get("variant_id")), d.get("qty", 1))})
    except (ValueError, TypeError) as e:
        return _err(e)


@store_bp.route("/cart/update", methods=["POST"])
@login_required
def cart_update():
    d = request.get_json(silent=True) or {}
    try:
        return jsonify({"success": True, "data": svc.update_cart_item(current_user.id, int(d.get("variant_id")), int(d.get("qty", 0)))})
    except (ValueError, TypeError) as e:
        return _err(e)


@store_bp.route("/cart/clear", methods=["POST"])
@login_required
def cart_clear():
    svc.clear_cart(current_user.id)
    return jsonify({"success": True, "data": svc.get_cart(current_user.id)})


# ---------------------------------------------------------------- addresses
@store_bp.route("/addresses")
@login_required
def addresses():
    return jsonify({"success": True, "data": svc.list_addresses(current_user.id)})


@store_bp.route("/addresses", methods=["POST"])
@login_required
def address_save():
    d = request.get_json(silent=True) or {}
    try:
        aid = svc.save_address(current_user.id, d, d.get("id"))
        return jsonify({"success": True, "id": aid, "data": svc.list_addresses(current_user.id)})
    except ValueError as e:
        return _err(e)


@store_bp.route("/addresses/<int:aid>/delete", methods=["POST"])
@login_required
def address_delete(aid):
    svc.delete_address(current_user.id, aid)
    return jsonify({"success": True, "data": svc.list_addresses(current_user.id)})


# ---------------------------------------------------------------- checkout
@store_bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    d = request.get_json(silent=True) or {}
    try:
        result = svc.place_order(
            current_user.id, d.get("address_id"), d.get("payment_method", "online"),
            d.get("wallet_amount"), d.get("note"),
        )
        gw = result["payment"].get("gateway")
        if gw:
            gw["key_id"] = current_app.config.get("RAZORPAY_KEY_ID", "")
            gw["name"] = "RK Trendz"
            gw["prefill"] = {"name": current_user.full_name, "email": current_user.email,
                             "contact": getattr(current_user, "phone", "") or ""}
        return jsonify({"success": True, **result})
    except ValueError as e:
        return _err(e)
    except Exception as e:
        logger.error("checkout failed user=%s: %s", current_user.id, e, exc_info=True)
        return _err("Checkout failed. Please try again.", 500)


@store_bp.route("/payment/verify", methods=["POST"])
@login_required
def payment_verify():
    """
    Client-side confirmation after Razorpay checkout. Signature is verified
    with RAZORPAY_KEY_SECRET when configured; the webhook remains the source
    of truth and is idempotent with this call.
    """
    d = request.get_json(silent=True) or {}
    goid, gpid, sig = d.get("gateway_order_id"), d.get("gateway_payment_id"), d.get("signature")
    if not goid or not gpid:
        return _err("Missing payment reference")
    secret = current_app.config.get("RAZORPAY_KEY_SECRET")
    if secret:
        expected = hmac.new(secret.encode(), f"{goid}|{gpid}".encode(), hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(expected, sig):
            return _err("Payment signature invalid", 400)
    elif current_app.config.get("ENV") == "production":
        return _err("Payment verification not configured", 500)
    try:
        r = svc.confirm_online_payment(goid, gpid)
        return jsonify(r)
    except ValueError as e:
        return _err(e)


# ---------------------------------------------------------------- orders
@store_bp.route("/orders")
@login_required
def my_orders():
    return jsonify({"success": True, **svc.list_my_orders(current_user.id, request.args.get("page", 1))})


@store_bp.route("/orders/<int:oid>")
@login_required
def my_order(oid):
    o = svc.get_order(current_user.id, oid)
    if not o:
        return _err("Order not found", 404)
    return jsonify({"success": True, "data": o})


@store_bp.route("/orders/<int:oid>/cancel", methods=["POST"])
@login_required
def my_order_cancel(oid):
    d = request.get_json(silent=True) or {}
    try:
        return jsonify(svc.cancel_order(current_user.id, oid, d.get("reason")))
    except ValueError as e:
        return _err(e)
