"""
app/services/store_service.py  —  E-COMMERCE + MLM ENGINE (NEW)

Catalog / cart / checkout / payment / fulfilment for the RK Trendz store, with
the MLM plan wired to cart value.

Business rules (soft-coded; every % / amount comes from the DB)
==============================================================
* Products live in 4 categories (Electrical, Clothes, Footwear, General).
* The member builds a cart. The cart total is compared with the plan tiers
  in `subscription_plans` (1800 / 3600 / 7200 / 14400 / 28800 ...):
    - activation_match_mode = 'exact' (default): the cart total must EQUAL a
      tier amount for that tier to activate/upgrade. The API tells the UI
      how much to add/remove to reach the nearest tiers.
    - 'floor': the highest tier <= cart total is used.
* order_kind:
    activation  : member not active yet and cart matched a tier
                  -> pays self cashback + direct (L1) + level income (L2..N)
                     on the ORDER amount, activates member, rank evaluation.
    upgrade     : member active, cart matched a HIGHER tier than current
                  -> same payouts as activation on the order amount, and the
                     member's plan moves up.
    repurchase  : any other paid order by an ACTIVE member
                  -> repurchase_cashback % to buyer + repurchase_referral % to
                     direct sponsor. Counts in business volume for ranks.
                     NO level income (per business rules).
* Inactive members can ONLY check out if the cart matches a tier (they must
  activate first).
* Payment: 'wallet' (earnings wallet, debited atomically), 'online' (Razorpay:
  order created -> paid webhook / verify -> fulfilled), or 'split'
  (wallet part now, online for the rest).
* Money truth: on payment success ONE row is written to `orders` (the
  financial anchor read by the P&L / rank volume / commissions) and linked to
  the shop order. Commissions are idempotent on (earner, order_id, level).
* Stock is reserved at payment time (row locks), released on cancel/refund.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP

from app.db import get_cursor
from app.cache import cache
from app.services.wallet_service import credit_wallet, debit_wallet, _calculate_balance

logger = logging.getLogger(__name__)

TWO = Decimal("0.01")
CATALOG_TTL = 60


def _d(v) -> Decimal:
    return Decimal(str(v if v is not None else 0))


def _m(v) -> Decimal:
    return _d(v).quantize(TWO, rounding=ROUND_HALF_UP)


def _f(v) -> float:
    return float(_m(v))


# ===========================================================================
# SETTINGS
# ===========================================================================
def get_store_settings(cur=None) -> dict:
    cached = cache.get("store:settings")
    if cached is not None:
        return cached

    def _load(c):
        c.execute("SELECT setting_key, setting_value FROM store_settings")
        return {r["setting_key"]: r["setting_value"] for r in c.fetchall()}

    if cur is not None:
        s = _load(cur)
    else:
        with get_cursor() as c:
            s = _load(c)
    cache.set("store:settings", s, timeout=CATALOG_TTL)
    return s


def update_store_settings(values: dict):
    with get_cursor() as cur:
        for k, v in values.items():
            cur.execute(
                """
                INSERT INTO store_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON CONFLICT (setting_key) DO UPDATE
                    SET setting_value = EXCLUDED.setting_value, updated_at = NOW()
                """,
                (k, str(v)),
            )
    cache.delete("store:settings")


# ===========================================================================
# CATALOG (public)
# ===========================================================================
def list_categories(include_inactive=False):
    with get_cursor() as cur:
        sql = """
            SELECT c.*, (SELECT COUNT(*) FROM products p
                         WHERE p.category_id = c.id AND p.is_active) AS product_count
            FROM product_categories c
        """
        if not include_inactive:
            sql += " WHERE c.is_active = TRUE"
        sql += " ORDER BY c.sort_order, c.name"
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def list_products(category=None, q=None, page=1, page_size=24, sort="newest",
                  min_price=None, max_price=None, featured=None, include_inactive=False):
    page = max(1, int(page or 1))
    page_size = max(1, min(60, int(page_size or 24)))
    where = ["1=1"] if include_inactive else ["p.is_active = TRUE"]
    params: list = []
    if category:
        if str(category).isdigit():
            where.append("p.category_id = %s")
            params.append(int(category))
        else:
            where.append("c.slug = %s")
            params.append(category)
    if q:
        where.append("(p.name ILIKE %s OR p.brand ILIKE %s OR p.description ILIKE %s)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if featured:
        where.append("p.is_featured = TRUE")
    having = []
    if min_price is not None:
        having.append("MIN(v.price) >= %s")
    if max_price is not None:
        having.append("MIN(v.price) <= %s")

    order = {
        "price_asc": "min_price ASC",
        "price_desc": "min_price DESC",
        "name": "p.name ASC",
        "newest": "p.created_at DESC",
    }.get(sort, "p.created_at DESC")

    base = f"""
        FROM products p
        JOIN product_categories c ON c.id = p.category_id
        LEFT JOIN product_variants v ON v.product_id = p.id AND v.is_active = TRUE
        WHERE {' AND '.join(where)}
        GROUP BY p.id, c.name, c.slug
        {('HAVING ' + ' AND '.join(having)) if having else ''}
    """
    hparams = []
    if min_price is not None:
        hparams.append(_d(min_price))
    if max_price is not None:
        hparams.append(_d(max_price))

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM (SELECT p.id {base}) t", params + hparams)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT p.id, p.name, p.slug, p.brand, p.gst_percent, p.is_featured, p.is_active,
                   p.created_at, c.name AS category_name, c.slug AS category_slug,
                   MIN(v.price) AS min_price, MAX(v.price) AS max_price, MAX(v.mrp) AS mrp,
                   COALESCE(SUM(v.stock_qty), 0) AS total_stock,
                   COUNT(v.id) AS variant_count,
                   (SELECT image_url FROM product_images i WHERE i.product_id = p.id
                    ORDER BY sort_order, id LIMIT 1) AS image_url
            {base}
            ORDER BY {order}
            LIMIT %s OFFSET %s
            """,
            params + hparams + [page_size, (page - 1) * page_size],
        )
        items = []
        for r in cur.fetchall():
            d = dict(r)
            for k in ("min_price", "max_price", "mrp", "gst_percent"):
                d[k] = _f(d[k]) if d.get(k) is not None else None
            d["in_stock"] = (d.get("total_stock") or 0) > 0
            items.append(d)
    return {"items": items, "page": page, "page_size": page_size, "total": total,
            "pages": max(1, -(-total // page_size))}


def get_product(product_id_or_slug, include_inactive=False):
    with get_cursor() as cur:
        col = "p.id" if str(product_id_or_slug).isdigit() else "p.slug"
        cur.execute(
            f"""
            SELECT p.*, c.name AS category_name, c.slug AS category_slug
            FROM products p JOIN product_categories c ON c.id = p.category_id
            WHERE {col} = %s {'' if include_inactive else 'AND p.is_active = TRUE'}
            """,
            (int(product_id_or_slug) if col == "p.id" else product_id_or_slug,),
        )
        p = cur.fetchone()
        if not p:
            return None
        p = dict(p)
        p["gst_percent"] = _f(p["gst_percent"])
        cur.execute(
            """
            SELECT id, sku, attributes, price, mrp, cost_price, stock_qty, is_active
            FROM product_variants WHERE product_id = %s
            {} ORDER BY id
            """.format("" if include_inactive else "AND is_active = TRUE"),
            (p["id"],),
        )
        variants = []
        for v in cur.fetchall():
            v = dict(v)
            v["price"] = _f(v["price"])
            v["mrp"] = _f(v["mrp"]) if v["mrp"] is not None else None
            if not include_inactive:
                v.pop("cost_price", None)  # never leak cost to the storefront
            else:
                v["cost_price"] = _f(v["cost_price"])
            v["label"] = " / ".join(str(x) for x in (v.get("attributes") or {}).values()) or "Standard"
            variants.append(v)
        p["variants"] = variants
        cur.execute(
            "SELECT id, image_url, variant_id, sort_order FROM product_images "
            "WHERE product_id = %s ORDER BY sort_order, id",
            (p["id"],),
        )
        p["images"] = [dict(r) for r in cur.fetchall()]
        p["highlights_list"] = [h.strip() for h in (p.get("highlights") or "").splitlines() if h.strip()]
        return p


# ===========================================================================
# PLAN MATCHING
# ===========================================================================
def _plans(cur):
    cur.execute(
        "SELECT id, name, price, product_cost, lucky_draw_coupons FROM subscription_plans "
        "WHERE is_active = TRUE ORDER BY price ASC"
    )
    return [dict(r) for r in cur.fetchall()]


def _member_state(cur, user_id):
    cur.execute(
        """
        SELECT u.id, u.is_active, u.package_id, u.sponsor_id,
               COALESCE(sp.price, 0) AS plan_price, sp.name AS plan_name
        FROM users u LEFT JOIN subscription_plans sp ON sp.id = u.package_id
        WHERE u.id = %s
        """,
        (user_id,),
    )
    return cur.fetchone()


def evaluate_plan_match(cur, user_id, subtotal: Decimal) -> dict:
    """
    Decide what a cart of `subtotal` does for this member.
    Returns dict(kind, plan, tiers, next_tier, add_to_reach, remove_to_reach,
                 can_checkout, reason)
    """
    settings = get_store_settings(cur)
    mode = (settings.get("activation_match_mode") or "exact").lower()
    plans = _plans(cur)
    me = _member_state(cur, user_id)
    is_active = bool(me and me["is_active"])
    current_price = _d(me["plan_price"]) if me else Decimal("0")
    subtotal = _m(subtotal)

    matched = None
    if mode == "floor":
        for p in plans:
            if _d(p["price"]) <= subtotal:
                matched = p
    else:
        for p in plans:
            if _m(p["price"]) == subtotal:
                matched = p
                break

    higher = [p for p in plans if _d(p["price"]) > subtotal]
    next_tier = higher[0] if higher else None
    lower = [p for p in plans if _d(p["price"]) < subtotal]
    prev_tier = lower[-1] if lower else None

    tiers = []
    for p in plans:
        price = _d(p["price"])
        tiers.append({
            "id": p["id"], "name": p["name"], "price": _f(price),
            "matched": bool(matched and matched["id"] == p["id"]),
            "is_current": bool(me and me["package_id"] == p["id"]),
            "is_upgrade": price > current_price,
            "diff": _f(price - subtotal),
        })

    if matched and not is_active:
        kind, plan = "activation", matched
    elif matched and is_active and _d(matched["price"]) > current_price:
        kind, plan = "upgrade", matched
    elif is_active:
        kind, plan = "repurchase", None
    else:
        kind, plan = "none", None

    min_rep = _d(settings.get("min_repurchase_amount") or 0)
    can_checkout = subtotal > 0 and (
        kind in ("activation", "upgrade") or (kind == "repurchase" and subtotal >= min_rep)
    )
    if kind == "none":
        reason = ("Your account is not active yet. Make your cart total exactly ₹%s "
                  "(or any plan amount) to activate and unlock all benefits."
                  % (_f(next_tier["price"]) if next_tier else "a plan amount"))
    elif kind == "repurchase" and subtotal < min_rep:
        reason = f"Minimum order amount is ₹{_f(min_rep)}."
    else:
        reason = None

    return {
        "mode": mode,
        "kind": kind,
        "plan": {"id": plan["id"], "name": plan["name"], "price": _f(plan["price"]),
                 "coupons": plan.get("lucky_draw_coupons")} if plan else None,
        "is_active_member": is_active,
        "current_plan": {"id": me["package_id"], "name": me["plan_name"],
                         "price": _f(current_price)} if me and me["package_id"] else None,
        "tiers": tiers,
        "next_tier": {"name": next_tier["name"], "price": _f(next_tier["price"]),
                      "add_to_reach": _f(_d(next_tier["price"]) - subtotal)} if next_tier else None,
        "prev_tier": {"name": prev_tier["name"], "price": _f(prev_tier["price"]),
                      "remove_to_reach": _f(subtotal - _d(prev_tier["price"]))} if prev_tier else None,
        "can_checkout": can_checkout,
        "reason": reason,
    }


# ===========================================================================
# CART
# ===========================================================================
def _cart_id(cur, user_id):
    cur.execute("SELECT id FROM carts WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO carts (user_id) VALUES (%s) RETURNING id", (user_id,))
    return cur.fetchone()["id"]


def _cart_lines(cur, user_id, lock=False):
    cur.execute(
        f"""
        SELECT ci.id AS item_id, ci.qty, v.id AS variant_id, v.sku, v.attributes,
               v.price, v.mrp, v.cost_price, v.stock_qty, v.is_active AS variant_active,
               p.id AS product_id, p.name AS product_name, p.gst_percent, p.is_active AS product_active,
               (SELECT image_url FROM product_images i WHERE i.product_id = p.id
                ORDER BY (i.variant_id = v.id) DESC NULLS LAST, sort_order, id LIMIT 1) AS image_url
        FROM cart_items ci
        JOIN carts c ON c.id = ci.cart_id
        JOIN product_variants v ON v.id = ci.variant_id
        JOIN products p ON p.id = v.product_id
        WHERE c.user_id = %s
        ORDER BY ci.added_at
        {'FOR UPDATE OF v' if lock else ''}
        """,
        (user_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def _price_lines(lines, settings):
    subtotal = Decimal("0")
    cost = Decimal("0")
    gst = Decimal("0")
    inclusive = (settings.get("prices_include_gst") or "true").lower() == "true"
    out = []
    for ln in lines:
        price = _d(ln["price"])
        qty = int(ln["qty"])
        line_total = _m(price * qty)
        rate = _d(ln["gst_percent"]) / Decimal("100")
        if inclusive:
            line_gst = _m(line_total - line_total / (1 + rate)) if rate else Decimal("0")
        else:
            line_gst = _m(line_total * rate)
        subtotal += line_total
        gst += line_gst
        cost += _m(_d(ln["cost_price"]) * qty)
        d = dict(ln)
        d["line_total"] = _f(line_total)
        d["line_gst"] = _f(line_gst)
        d["price"] = _f(price)
        d["mrp"] = _f(d["mrp"]) if d.get("mrp") is not None else None
        d["label"] = " / ".join(str(x) for x in (d.get("attributes") or {}).values()) or "Standard"
        d["available"] = bool(d["variant_active"] and d["product_active"])
        d["stock_ok"] = d["stock_qty"] >= qty
        d.pop("cost_price", None)
        out.append(d)
    return out, subtotal, gst, cost


def _shipping(settings, subtotal: Decimal) -> Decimal:
    fee = _d(settings.get("shipping_fee") or 0)
    free_above = _d(settings.get("free_shipping_above") or 0)
    if fee <= 0:
        return Decimal("0")
    if free_above > 0 and subtotal >= free_above:
        return Decimal("0")
    return _m(fee)


def get_cart(user_id):
    with get_cursor() as cur:
        settings = get_store_settings(cur)
        lines = _cart_lines(cur, user_id)
        items, subtotal, gst, _cost = _price_lines(lines, settings)
        ship = _shipping(settings, subtotal)
        match = evaluate_plan_match(cur, user_id, subtotal)
        balance = _calculate_balance(cur, user_id)
        return {
            "items": items,
            "item_count": sum(i["qty"] for i in items),
            "subtotal": _f(subtotal),
            "gst_included": _f(gst),
            "shipping_fee": _f(ship),
            "total": _f(subtotal + ship),
            "wallet_balance": _f(balance),
            "plan_match": match,
            "all_available": all(i["available"] and i["stock_ok"] for i in items),
        }


def add_to_cart(user_id, variant_id, qty=1):
    qty = int(qty or 1)
    if qty <= 0:
        raise ValueError("Quantity must be at least 1")
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT v.id, v.stock_qty, v.is_active, p.is_active AS p_active
            FROM product_variants v JOIN products p ON p.id = v.product_id
            WHERE v.id = %s
            """,
            (variant_id,),
        )
        v = cur.fetchone()
        if not v or not v["is_active"] or not v["p_active"]:
            raise ValueError("This product is not available")
        cid = _cart_id(cur, user_id)
        cur.execute(
            "SELECT qty FROM cart_items WHERE cart_id = %s AND variant_id = %s",
            (cid, variant_id),
        )
        row = cur.fetchone()
        new_qty = qty + (row["qty"] if row else 0)
        if new_qty > v["stock_qty"]:
            raise ValueError(f"Only {v['stock_qty']} left in stock")
        cur.execute(
            """
            INSERT INTO cart_items (cart_id, variant_id, qty) VALUES (%s, %s, %s)
            ON CONFLICT (cart_id, variant_id) DO UPDATE SET qty = EXCLUDED.qty
            """,
            (cid, variant_id, new_qty),
        )
        cur.execute("UPDATE carts SET updated_at = NOW() WHERE id = %s", (cid,))
    return get_cart(user_id)


def update_cart_item(user_id, variant_id, qty):
    qty = int(qty)
    with get_cursor() as cur:
        cid = _cart_id(cur, user_id)
        if qty <= 0:
            cur.execute("DELETE FROM cart_items WHERE cart_id = %s AND variant_id = %s", (cid, variant_id))
        else:
            cur.execute("SELECT stock_qty FROM product_variants WHERE id = %s", (variant_id,))
            v = cur.fetchone()
            if not v:
                raise ValueError("Product not found")
            if qty > v["stock_qty"]:
                raise ValueError(f"Only {v['stock_qty']} left in stock")
            cur.execute(
                "UPDATE cart_items SET qty = %s WHERE cart_id = %s AND variant_id = %s",
                (qty, cid, variant_id),
            )
        cur.execute("UPDATE carts SET updated_at = NOW() WHERE id = %s", (cid,))
    return get_cart(user_id)


def clear_cart(user_id, cur=None):
    def _do(c):
        c.execute("DELETE FROM cart_items WHERE cart_id IN (SELECT id FROM carts WHERE user_id = %s)", (user_id,))
    if cur is not None:
        _do(cur)
    else:
        with get_cursor() as c:
            _do(c)


# ===========================================================================
# ADDRESSES
# ===========================================================================
def list_addresses(user_id):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM user_addresses WHERE user_id = %s ORDER BY is_default DESC, id DESC",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def save_address(user_id, data: dict, address_id=None):
    required = ("full_name", "phone", "line1", "city", "state", "pincode")
    missing = [k for k in required if not str(data.get(k) or "").strip()]
    if missing:
        raise ValueError("Missing: " + ", ".join(missing))
    with get_cursor() as cur:
        if data.get("is_default"):
            cur.execute("UPDATE user_addresses SET is_default = FALSE WHERE user_id = %s", (user_id,))
        cur.execute("SELECT COUNT(*) AS n FROM user_addresses WHERE user_id = %s", (user_id,))
        first = cur.fetchone()["n"] == 0
        vals = (data["full_name"].strip(), data["phone"].strip(), data["line1"].strip(),
                (data.get("line2") or "").strip() or None, (data.get("landmark") or "").strip() or None,
                data["city"].strip(), data["state"].strip(), str(data["pincode"]).strip(),
                bool(data.get("is_default")) or first)
        if address_id:
            cur.execute(
                """
                UPDATE user_addresses SET full_name=%s, phone=%s, line1=%s, line2=%s, landmark=%s,
                       city=%s, state=%s, pincode=%s, is_default=%s
                WHERE id = %s AND user_id = %s RETURNING id
                """,
                vals + (address_id, user_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO user_addresses (user_id, full_name, phone, line1, line2, landmark,
                                            city, state, pincode, is_default)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (user_id,) + vals,
            )
        row = cur.fetchone()
        return row["id"] if row else None


def delete_address(user_id, address_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM user_addresses WHERE id = %s AND user_id = %s", (address_id, user_id))


# ===========================================================================
# CHECKOUT
# ===========================================================================
def _next_order_no(cur):
    cur.execute("SELECT nextval('shop_order_no_seq') AS n")
    return f"RKT{time.strftime('%y%m')}{cur.fetchone()['n']:06d}"


def _event(cur, order_id, status, note=None, actor="system"):
    cur.execute(
        "INSERT INTO shop_order_events (order_id, status, note, actor) VALUES (%s, %s, %s, %s)",
        (order_id, status, note, actor),
    )


def place_order(user_id, address_id, payment_method="online", wallet_amount=None,
                customer_note=None):
    """
    Create a shop order from the cart.
      payment_method: 'wallet' | 'online' | 'split'
    Returns {order, payment: {method, wallet_paid, online_due, gateway...}}
    Wallet money is taken immediately (atomic). Online part is settled by
    confirm_online_payment() (webhook / client verify).
    """
    payment_method = (payment_method or "online").lower()
    if payment_method not in ("wallet", "online", "split"):
        raise ValueError("Invalid payment method")

    with get_cursor() as cur:
        settings = get_store_settings(cur)
        cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
        lines = _cart_lines(cur, user_id, lock=True)
        if not lines:
            raise ValueError("Your cart is empty")
        items, subtotal, gst, cost = _price_lines(lines, settings)
        for it in items:
            if not it["available"]:
                raise ValueError(f"{it['product_name']} is no longer available")
            if not it["stock_ok"]:
                raise ValueError(f"Only {it['stock_qty']} left of {it['product_name']}")

        match = evaluate_plan_match(cur, user_id, subtotal)
        if not match["can_checkout"]:
            raise ValueError(match["reason"] or "Cart does not qualify for checkout")

        cur.execute("SELECT * FROM user_addresses WHERE id = %s AND user_id = %s", (address_id, user_id))
        addr = cur.fetchone()
        if not addr:
            raise ValueError("Please select a delivery address")
        addr = {k: (str(v) if k in ("created_at",) else v) for k, v in dict(addr).items()}

        ship = _shipping(settings, subtotal)
        total = _m(subtotal + ship)

        # ---- decide wallet / online split ----
        balance = _calculate_balance(cur, user_id)
        if payment_method == "wallet":
            wallet_part = total
        elif payment_method == "split":
            wallet_part = _m(wallet_amount if wallet_amount is not None else min(balance, total))
            wallet_part = max(Decimal("0"), min(wallet_part, total))
        else:
            wallet_part = Decimal("0")
        if wallet_part > balance:
            raise ValueError(f"Insufficient wallet balance (₹{_f(balance)} available)")
        online_part = _m(total - wallet_part)
        if payment_method == "wallet" and online_part > 0:
            raise ValueError("Wallet balance does not cover the order total")

        order_no = _next_order_no(cur)
        cur.execute(
            """
            INSERT INTO shop_orders (order_no, user_id, subtotal, gst_amount, shipping_fee, discount,
                                     total, cost_total, order_kind, plan_id, payment_method,
                                     payment_status, order_status, wallet_paid, online_paid,
                                     shipping_address, customer_note)
            VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, 'pending', 'placed', 0, 0, %s, %s)
            RETURNING id
            """,
            (order_no, user_id, subtotal, gst, ship, total, cost,
             match["kind"], match["plan"]["id"] if match["plan"] else None,
             payment_method, json.dumps(addr, default=str), (customer_note or "")[:500] or None),
        )
        order_id = cur.fetchone()["id"]

        for it in items:
            cur.execute(
                """
                INSERT INTO shop_order_items (order_id, product_id, variant_id, product_name,
                                              variant_label, sku, image_url, qty, unit_price,
                                              unit_cost, gst_percent, line_total)
                SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, v.cost_price, %s, %s
                FROM product_variants v WHERE v.id = %s
                """,
                (order_id, it["product_id"], it["variant_id"], it["product_name"], it["label"],
                 it["sku"], it["image_url"], it["qty"], it["price"], it["gst_percent"],
                 it["line_total"], it["variant_id"]),
            )
            # reserve stock now (released on cancel / failed payment)
            cur.execute(
                "UPDATE product_variants SET stock_qty = stock_qty - %s WHERE id = %s AND stock_qty >= %s",
                (it["qty"], it["variant_id"], it["qty"]),
            )
            if cur.rowcount != 1:
                raise ValueError(f"Stock changed for {it['product_name']}, please retry")

        _event(cur, order_id, "placed", f"Order placed ({match['kind']})", "member")

        # ---- wallet part (immediate, atomic) ----
        if wallet_part > 0:
            debit_wallet(cur, user_id, wallet_part, f"SHOP-{order_no}",
                         f"Purchase {order_no}" + (" (part payment)" if online_part > 0 else ""))
            cur.execute("UPDATE shop_orders SET wallet_paid = %s WHERE id = %s", (wallet_part, order_id))
            _event(cur, order_id, "wallet_paid", f"₹{_f(wallet_part)} paid from wallet", "member")

        gateway = None
        if online_part > 0:
            # Client-side Razorpay checkout uses this reference; the webhook /
            # verify endpoint completes the order.
            gateway_order_id = f"order_{order_no}_{uuid.uuid4().hex[:8]}"
            cur.execute(
                "UPDATE shop_orders SET gateway = 'razorpay', gateway_order_id = %s WHERE id = %s",
                (gateway_order_id, order_id),
            )
            gateway = {"provider": "razorpay", "gateway_order_id": gateway_order_id,
                       "amount_paise": int(online_part * 100), "currency": "INR"}
        else:
            _settle_paid_order(cur, order_id)

        clear_cart(user_id, cur)

    return {"order": get_order(user_id, order_id),
            "payment": {"method": payment_method, "wallet_paid": _f(wallet_part),
                        "online_due": _f(online_part), "gateway": gateway}}


def confirm_online_payment(gateway_order_id, gateway_payment_id, amount_paise=None):
    """Called by the payment webhook / verify endpoint once money is captured."""
    with get_cursor() as cur:
        cur.execute("SELECT id, total, wallet_paid, payment_status FROM shop_orders "
                    "WHERE gateway_order_id = %s FOR UPDATE", (gateway_order_id,))
        o = cur.fetchone()
        if not o:
            raise ValueError("Unknown gateway order")
        if o["payment_status"] == "paid":
            return {"success": True, "already": True, "order_id": o["id"]}
        due = _m(_d(o["total"]) - _d(o["wallet_paid"]))
        if amount_paise is not None and int(amount_paise) < int(due * 100):
            cur.execute("UPDATE shop_orders SET payment_status = 'review', admin_note = %s WHERE id = %s",
                        (f"Gateway paid {int(amount_paise)/100:.2f} but due {due}", o["id"]))
            _event(cur, o["id"], "review", "Amount mismatch — needs admin review")
            return {"success": False, "message": "Amount mismatch"}
        cur.execute(
            "UPDATE shop_orders SET online_paid = %s, gateway_payment_id = %s WHERE id = %s",
            (due, gateway_payment_id, o["id"]),
        )
        _event(cur, o["id"], "online_paid", f"₹{_f(due)} received via gateway ({gateway_payment_id})")
        _settle_paid_order(cur, o["id"])
        return {"success": True, "order_id": o["id"]}


def _settle_paid_order(cur, shop_order_id):
    """
    Money received in full -> write the financial anchor `orders` row, apply
    the MLM effects (activation / upgrade / repurchase), mark order confirmed.
    Idempotent: guarded by payment_status.
    """
    from app.services.commission_engine import distribute_commission, distribute_repurchase
    from app.services.rank_service import evaluate_user_rank_and_bonus

    cur.execute("SELECT * FROM shop_orders WHERE id = %s FOR UPDATE", (shop_order_id,))
    o = cur.fetchone()
    if not o or o["payment_status"] == "paid":
        return
    user_id = o["user_id"]

    cur.execute(
        """
        INSERT INTO orders (user_id, package_id, amount, status, payment_ref, shop_order_id,
                            cost_amount, gst_amount, order_kind)
        VALUES (%s, %s, %s, 'completed', %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (user_id, o["plan_id"], o["subtotal"], o["order_no"], shop_order_id,
         o["cost_total"], o["gst_amount"], o["order_kind"]),
    )
    mlm_order_id = cur.fetchone()["id"]

    if o["order_kind"] in ("activation", "upgrade") and o["plan_id"]:
        cur.execute(
            """
            UPDATE users SET package_id = %s, is_active = TRUE,
                   activated_at = COALESCE(activated_at, NOW())
            WHERE id = %s
            """,
            (o["plan_id"], user_id),
        )
        cur.execute(
            "INSERT INTO user_packages (user_id, package_id, amount, created_at) VALUES (%s, %s, %s, NOW())",
            (user_id, o["plan_id"], o["subtotal"]),
        )
        res = distribute_commission(buyer_id=user_id, package_id=o["plan_id"],
                                    order_id=mlm_order_id, cur=cur, amount=_d(o["subtotal"]))
        if res.get("status") == "error":
            raise RuntimeError(res.get("message", "Commission error"))
    else:
        res = distribute_repurchase(buyer_id=user_id, order_id=mlm_order_id,
                                    amount=_d(o["subtotal"]), cur=cur)
        if res.get("status") == "error":
            raise RuntimeError(res.get("message", "Repurchase commission error"))

    # Business volume changed for the whole upline -> re-evaluate ranks.
    try:
        from app.services.sponsor_service import get_sponsor_chain
        for sp in get_sponsor_chain(user_id, cur=cur):
            evaluate_user_rank_and_bonus(sp["user_id"], cur=cur)
        evaluate_user_rank_and_bonus(user_id, cur=cur)
    except Exception as e:
        logger.warning("rank re-evaluation skipped: %s", e)

    cur.execute(
        """
        UPDATE shop_orders SET payment_status = 'paid', order_status = 'confirmed',
               paid_at = NOW(), mlm_order_id = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (mlm_order_id, shop_order_id),
    )
    _event(cur, shop_order_id, "confirmed", "Payment complete — order confirmed")
    try:
        from app.services.notification_service import create_notification
        create_notification(user_id, "Order confirmed",
                            f"Your order {o['order_no']} is confirmed.", "order")
    except Exception:
        pass


# ===========================================================================
# ORDERS (member)
# ===========================================================================
def get_order(user_id, order_id, admin=False):
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT so.*, u.full_name, u.email, u.phone, sp.name AS plan_name
            FROM shop_orders so
            JOIN users u ON u.id = so.user_id
            LEFT JOIN subscription_plans sp ON sp.id = so.plan_id
            WHERE so.id = %s {'' if admin else 'AND so.user_id = %s'}
            """,
            (order_id,) if admin else (order_id, user_id),
        )
        o = cur.fetchone()
        if not o:
            return None
        o = dict(o)
        for k in ("subtotal", "gst_amount", "shipping_fee", "discount", "total", "wallet_paid",
                  "online_paid", "cost_total"):
            o[k] = _f(o[k])
        if not admin:
            o.pop("cost_total", None)
        cur.execute("SELECT * FROM shop_order_items WHERE order_id = %s ORDER BY id", (order_id,))
        items = []
        for it in cur.fetchall():
            it = dict(it)
            for k in ("unit_price", "line_total", "gst_percent", "unit_cost"):
                it[k] = _f(it[k])
            if not admin:
                it.pop("unit_cost", None)
            items.append(it)
        o["items"] = items
        cur.execute("SELECT status, note, actor, created_at FROM shop_order_events "
                    "WHERE order_id = %s ORDER BY created_at, id", (order_id,))
        o["events"] = [dict(r) for r in cur.fetchall()]
        return o


def list_my_orders(user_id, page=1, page_size=20):
    page = max(1, int(page or 1))
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE user_id = %s", (user_id,))
        total = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT so.id, so.order_no, so.total, so.order_kind, so.payment_status, so.order_status,
                   so.created_at, so.paid_at, so.delivered_at, sp.name AS plan_name,
                   (SELECT COUNT(*) FROM shop_order_items i WHERE i.order_id = so.id) AS item_count,
                   (SELECT image_url FROM shop_order_items i WHERE i.order_id = so.id ORDER BY id LIMIT 1) AS image_url,
                   (SELECT product_name FROM shop_order_items i WHERE i.order_id = so.id ORDER BY id LIMIT 1) AS first_item
            FROM shop_orders so LEFT JOIN subscription_plans sp ON sp.id = so.plan_id
            WHERE so.user_id = %s ORDER BY so.created_at DESC LIMIT %s OFFSET %s
            """,
            (user_id, page_size, (page - 1) * page_size),
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["total"] = _f(d["total"])
            rows.append(d)
    return {"items": rows, "total": total, "page": page,
            "pages": max(1, -(-total // page_size))}


def cancel_order(user_id, order_id, reason=None, admin_id=None):
    """Member can cancel before shipping; admin any time before delivery. Refunds wallet part."""
    try:
        user_id = int(user_id)          # current_user.id may arrive as a string
    except (TypeError, ValueError):
        pass
    with get_cursor() as cur:
        cur.execute("SELECT * FROM shop_orders WHERE id = %s FOR UPDATE", (order_id,))
        o = cur.fetchone()
        if not o or (admin_id is None and int(o["user_id"]) != int(user_id)):
            raise ValueError("Order not found")
        if o["order_status"] in ("shipped", "delivered", "cancelled"):
            raise ValueError(f"Order cannot be cancelled once {o['order_status']}")
        if o["payment_status"] == "paid" and admin_id is None:
            # Paid + confirmed: member cancels -> allowed only if not packed
            if o["order_status"] not in ("placed", "confirmed"):
                raise ValueError("Order is being packed; contact support to cancel")
        # release stock
        cur.execute("SELECT variant_id, qty FROM shop_order_items WHERE order_id = %s", (order_id,))
        for it in cur.fetchall():
            if it["variant_id"]:
                cur.execute("UPDATE product_variants SET stock_qty = stock_qty + %s WHERE id = %s",
                            (it["qty"], it["variant_id"]))
        # refund the WALLET part immediately; the ONLINE part is refunded at
        # the gateway by the admin (never both — that would double-refund).
        refunded = Decimal("0")
        paid_wallet = _d(o["wallet_paid"])
        paid_online = _d(o["online_paid"])
        if paid_wallet > 0:
            credit_wallet(cur, o["user_id"], paid_wallet, f"REFUND-W-{o['order_no']}",
                          f"Refund for cancelled order {o['order_no']}")
            refunded += paid_wallet
        refund_pending = Decimal("0")
        if paid_online > 0:
            refund_pending = paid_online
            _event(cur, order_id, "refund_pending",
                   f"₹{_f(paid_online)} to be refunded to the original payment method by admin",
                   "system")
        # reverse the financial anchor + commissions if it had been settled
        if o["payment_status"] == "paid" and o["mlm_order_id"]:
            _reverse_settled_order(cur, o)
        cur.execute(
            """
            UPDATE shop_orders SET order_status = 'cancelled',
                   payment_status = CASE
                       WHEN %s > 0 AND %s = 0 THEN 'refunded'
                       WHEN %s > 0 THEN 'refund_pending'
                       ELSE payment_status END,
                   cancelled_at = NOW(), admin_note = COALESCE(%s, admin_note), updated_at = NOW()
            WHERE id = %s
            """,
            (refunded, refund_pending, refund_pending, reason, order_id),
        )
        _event(cur, order_id, "cancelled", reason or "Cancelled",
               f"admin:{admin_id}" if admin_id else "member")
    return {"success": True, "refunded": _f(refunded), "refund_pending": _f(refund_pending)}


def _reverse_settled_order(cur, o):
    """Claw back commissions paid for this order and void the anchor row."""
    cur.execute("SELECT id, earner_id, amount, level FROM commissions WHERE order_id = %s", (o["mlm_order_id"],))
    for cm in cur.fetchall():
        try:
            debit_wallet(cur, cm["earner_id"], _d(cm["amount"]), f"CLAWBACK-{o['order_no']}-{cm['id']}",
                         f"Commission reversed: order {o['order_no']} cancelled")
        except Exception as e:
            # insufficient balance -> record negative adjustment via ledger row w/ closing balance
            logger.warning("clawback shortfall earner=%s: %s", cm["earner_id"], e)
            cur.execute(
                """
                INSERT INTO wallet_ledger (user_id, amount, transaction_type, reference_id, description)
                VALUES (%s, %s, 'debit', %s, %s)
                """,
                (cm["earner_id"], -_d(cm["amount"]), f"CLAWBACK-{o['order_no']}-{cm['id']}",
                 f"Commission reversed (negative balance): order {o['order_no']} cancelled"),
            )
    cur.execute("DELETE FROM commissions WHERE order_id = %s", (o["mlm_order_id"],))
    cur.execute("UPDATE orders SET status = 'cancelled' WHERE id = %s", (o["mlm_order_id"],))
    if o["order_kind"] in ("activation", "upgrade"):
        cur.execute("DELETE FROM user_packages WHERE user_id = %s AND package_id = %s AND amount = %s "
                    "AND id = (SELECT MAX(id) FROM user_packages WHERE user_id = %s AND package_id = %s)",
                    (o["user_id"], o["plan_id"], o["subtotal"], o["user_id"], o["plan_id"]))
        # roll plan back to the highest remaining paid plan (or inactive)
        cur.execute(
            """
            SELECT up.package_id FROM user_packages up JOIN subscription_plans sp ON sp.id = up.package_id
            WHERE up.user_id = %s ORDER BY sp.price DESC LIMIT 1
            """,
            (o["user_id"],),
        )
        prev = cur.fetchone()
        if prev:
            cur.execute("UPDATE users SET package_id = %s WHERE id = %s", (prev["package_id"], o["user_id"]))
        else:
            cur.execute("UPDATE users SET package_id = NULL, is_active = FALSE WHERE id = %s", (o["user_id"],))


# ===========================================================================
# ADMIN: catalogue management
# ===========================================================================
def _slugify(s: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or uuid.uuid4().hex[:8]


def admin_save_category(data: dict, category_id=None):
    with get_cursor() as cur:
        slug = _slugify(data.get("slug") or data.get("name"))
        vals = (data["name"].strip(), slug, data.get("description"), data.get("icon"),
                int(data.get("sort_order") or 0), bool(data.get("is_active", True)))
        if category_id:
            cur.execute(
                """UPDATE product_categories SET name=%s, slug=%s, description=%s, icon=%s,
                   sort_order=%s, is_active=%s WHERE id=%s RETURNING id""", vals + (category_id,))
        else:
            cur.execute(
                """INSERT INTO product_categories (name, slug, description, icon, sort_order, is_active)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""", vals)
        return cur.fetchone()["id"]


def admin_save_product(data: dict, product_id=None):
    with get_cursor() as cur:
        slug = _slugify(data.get("slug") or data.get("name"))
        if not product_id:
            cur.execute("SELECT 1 FROM products WHERE slug = %s", (slug,))
            if cur.fetchone():
                slug = f"{slug}-{uuid.uuid4().hex[:4]}"
        vals = (int(data["category_id"]), data["name"].strip(), slug, (data.get("brand") or "").strip() or None,
                data.get("description"), data.get("highlights"), _d(data.get("gst_percent") or 18),
                (data.get("hsn_code") or "").strip() or None, bool(data.get("is_active", True)),
                bool(data.get("is_featured", False)))
        if product_id:
            cur.execute(
                """UPDATE products SET category_id=%s, name=%s, slug=%s, brand=%s, description=%s,
                   highlights=%s, gst_percent=%s, hsn_code=%s, is_active=%s, is_featured=%s,
                   updated_at=NOW() WHERE id=%s RETURNING id""", vals + (product_id,))
        else:
            cur.execute(
                """INSERT INTO products (category_id, name, slug, brand, description, highlights,
                   gst_percent, hsn_code, is_active, is_featured)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""", vals)
        pid = cur.fetchone()["id"]
    cache.delete("store:settings")
    return pid


def admin_save_variant(product_id, data: dict, variant_id=None):
    attrs = data.get("attributes") or {}
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs) if attrs.strip().startswith("{") else \
                dict(kv.split(":", 1) for kv in attrs.split(",") if ":" in kv)
        except Exception:
            attrs = {}
    attrs = {str(k).strip(): str(v).strip() for k, v in attrs.items() if str(k).strip()}
    price = _m(data.get("price"))
    if price <= 0:
        raise ValueError("Price must be greater than 0")
    with get_cursor() as cur:
        sku = (data.get("sku") or "").strip() or f"SKU-{product_id}-{uuid.uuid4().hex[:6].upper()}"
        vals = (sku, json.dumps(attrs), price,
                _m(data["mrp"]) if data.get("mrp") not in (None, "") else None,
                _m(data.get("cost_price") or 0), int(data.get("stock_qty") or 0),
                bool(data.get("is_active", True)))
        if variant_id:
            cur.execute(
                """UPDATE product_variants SET sku=%s, attributes=%s, price=%s, mrp=%s, cost_price=%s,
                   stock_qty=%s, is_active=%s WHERE id=%s AND product_id=%s RETURNING id""",
                vals + (variant_id, product_id))
        else:
            cur.execute(
                """INSERT INTO product_variants (product_id, sku, attributes, price, mrp, cost_price,
                   stock_qty, is_active) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (product_id,) + vals)
        row = cur.fetchone()
        return row["id"] if row else None


def admin_delete_variant(product_id, variant_id):
    """Deactivate if referenced by orders (never lose history); else hard delete."""
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM shop_order_items WHERE variant_id = %s LIMIT 1", (variant_id,))
        if cur.fetchone():
            cur.execute("UPDATE product_variants SET is_active = FALSE WHERE id = %s AND product_id = %s",
                        (variant_id, product_id))
            return "archived"
        cur.execute("DELETE FROM product_variants WHERE id = %s AND product_id = %s", (variant_id, product_id))
        return "deleted"


def admin_delete_product(product_id):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM shop_order_items WHERE product_id = %s LIMIT 1", (product_id,))
        if cur.fetchone():
            cur.execute("UPDATE products SET is_active = FALSE, updated_at = NOW() WHERE id = %s", (product_id,))
            return "archived"
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        return "deleted"


def admin_add_image(product_id, image_url, variant_id=None):
    with get_cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS s FROM product_images WHERE product_id = %s",
                    (product_id,))
        s = cur.fetchone()["s"]
        cur.execute(
            "INSERT INTO product_images (product_id, variant_id, image_url, sort_order) VALUES (%s,%s,%s,%s) RETURNING id",
            (product_id, variant_id or None, image_url, s))
        return cur.fetchone()["id"]


def admin_delete_image(image_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM product_images WHERE id = %s RETURNING image_url", (image_id,))
        row = cur.fetchone()
        return row["image_url"] if row else None


# ===========================================================================
# ADMIN: orders / fulfilment
# ===========================================================================
ORDER_FLOW = ["placed", "confirmed", "packed", "shipped", "delivered"]


def admin_list_orders(status=None, payment_status=None, q=None, page=1, page_size=30):
    page = max(1, int(page or 1))
    where, params = ["1=1"], []
    if status:
        where.append("so.order_status = %s"); params.append(status)
    if payment_status:
        where.append("so.payment_status = %s"); params.append(payment_status)
    if q:
        where.append("(so.order_no ILIKE %s OR u.full_name ILIKE %s OR u.phone ILIKE %s OR u.email ILIKE %s)")
        params += [f"%{q}%"] * 4
    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM shop_orders so JOIN users u ON u.id = so.user_id WHERE {' AND '.join(where)}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT so.id, so.order_no, so.total, so.subtotal, so.cost_total, so.order_kind, so.payment_method,
                   so.payment_status, so.order_status, so.created_at, so.paid_at, so.tracking_no, so.courier,
                   u.id AS user_id, u.full_name, u.phone, u.email, sp.name AS plan_name,
                   (SELECT COUNT(*) FROM shop_order_items i WHERE i.order_id = so.id) AS item_count
            FROM shop_orders so JOIN users u ON u.id = so.user_id
            LEFT JOIN subscription_plans sp ON sp.id = so.plan_id
            WHERE {' AND '.join(where)}
            ORDER BY so.created_at DESC LIMIT %s OFFSET %s
            """,
            params + [page_size, (page - 1) * page_size],
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            for k in ("total", "subtotal", "cost_total"):
                d[k] = _f(d[k])
            rows.append(d)
        cur.execute(
            """
            SELECT order_status, COUNT(*) AS n FROM shop_orders GROUP BY order_status
            """
        )
        counts = {r["order_status"]: r["n"] for r in cur.fetchall()}
    return {"items": rows, "total": total, "page": page, "pages": max(1, -(-total // page_size)),
            "counts": counts}


def admin_update_order_status(order_id, new_status, admin_id, courier=None, tracking_no=None, note=None):
    new_status = (new_status or "").lower()
    if new_status not in ORDER_FLOW:
        raise ValueError("Invalid status")
    with get_cursor() as cur:
        cur.execute("SELECT * FROM shop_orders WHERE id = %s FOR UPDATE", (order_id,))
        o = cur.fetchone()
        if not o:
            raise ValueError("Order not found")
        if o["order_status"] == "cancelled":
            raise ValueError("Order is cancelled")
        if o["payment_status"] != "paid" and new_status != "placed":
            raise ValueError("Order is not paid yet")
        if ORDER_FLOW.index(new_status) < ORDER_FLOW.index(o["order_status"]):
            raise ValueError("Cannot move an order backwards")
        sets = ["order_status = %s", "updated_at = NOW()"]
        params = [new_status]
        if new_status == "shipped":
            sets += ["shipped_at = NOW()", "courier = %s", "tracking_no = %s"]
            params += [courier, tracking_no]
        if new_status == "delivered":
            sets.append("delivered_at = NOW()")
        if note:
            sets.append("admin_note = %s"); params.append(note)
        cur.execute(f"UPDATE shop_orders SET {', '.join(sets)} WHERE id = %s", params + [order_id])
        _event(cur, order_id, new_status,
               (f"Shipped via {courier} ({tracking_no})" if new_status == "shipped" else note),
               f"admin:{admin_id}")
        try:
            from app.services.notification_service import create_notification
            create_notification(o["user_id"], f"Order {new_status}",
                                f"Your order {o['order_no']} is now {new_status}.", "order")
        except Exception:
            pass
    return True


def admin_mark_paid(order_id, admin_id, note=None):
    """Manually settle an online order (e.g. bank transfer confirmed)."""
    with get_cursor() as cur:
        cur.execute("SELECT id, total, wallet_paid, payment_status FROM shop_orders WHERE id = %s FOR UPDATE", (order_id,))
        o = cur.fetchone()
        if not o:
            raise ValueError("Order not found")
        if o["payment_status"] == "paid":
            return True
        due = _m(_d(o["total"]) - _d(o["wallet_paid"]))
        cur.execute("UPDATE shop_orders SET online_paid = %s, gateway = COALESCE(gateway,'manual') WHERE id = %s",
                    (due, order_id))
        _event(cur, order_id, "online_paid", note or f"₹{_f(due)} marked received by admin", f"admin:{admin_id}")
        _settle_paid_order(cur, order_id)
    return True


def store_dashboard_stats():
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE payment_status='paid') AS paid_orders,
              COALESCE(SUM(total) FILTER (WHERE payment_status='paid'),0) AS gross_sales,
              COALESCE(SUM(subtotal - cost_total) FILTER (WHERE payment_status='paid'),0) AS gross_margin,
              COUNT(*) FILTER (WHERE order_status IN ('confirmed','packed')) AS to_ship,
              COUNT(*) FILTER (WHERE payment_status='pending') AS awaiting_payment,
              COUNT(*) FILTER (WHERE payment_status='review') AS needs_review
            FROM shop_orders
            """
        )
        s = dict(cur.fetchone())
        for k in ("gross_sales", "gross_margin"):
            s[k] = _f(s[k])
        cur.execute("SELECT COUNT(*) AS n FROM product_variants WHERE is_active AND stock_qty <= 5")
        s["low_stock"] = cur.fetchone()["n"]
        return s
