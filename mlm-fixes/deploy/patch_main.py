#!/usr/bin/env python3
"""
Safely patch the member-facing route files:

  app/routes/main.py
    1. Remove the DUPLICATE team/genealogy routes (handled by team_routes.py).
    2. check_session: let not-yet-activated members stay logged in.
    3. Upgrade the Razorpay webhook so a captured payment settles a STORE order
       and still supports legacy package payments.

  app/routes/auth_routes.py (found next to main.py)
    4. /me: keep pre-activation members logged in and add is_active to the
       payload (the frontend needs it to show the "Activate your plan" state).

Backs every file up first. Idempotent (safe to run twice).
"""
import sys, time, shutil, os, re

WEBHOOK_BLOCK = '''@main.route('/webhook/payment', methods=['POST'])
def payment_webhook():
    """Server-to-Server Payment Gateway Webhook (Razorpay).
    Settles STORE orders (e-commerce checkout) and legacy package payments."""
    from app.services import store_service
    payload = request.get_data(as_text=True)
    received_signature = request.headers.get('X-Razorpay-Signature')

    if not received_signature:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    try:
        secret = current_app.config.get('PAYMENT_GATEWAY_SECRET') or ''
        if not secret:
            logger.error("Webhook secret not configured (RAZORPAY_WEBHOOK_SECRET)")
            return jsonify({"status": "error", "message": "Webhook not configured"}), 500
        expected_signature = hmac.new(bytes(secret, 'utf-8'), msg=bytes(payload, 'utf-8'),
                                      digestmod=hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, received_signature):
            return jsonify({"status": "error", "message": "Invalid Signature"}), 400

        data = json.loads(payload)
        event_type = data.get('event')

        if event_type in ['payment.captured', 'order.paid']:
            payment_entity = data['payload']['payment']['entity']
            notes = payment_entity.get('notes') or {}
            gateway_order_id = notes.get('gateway_order_id') or payment_entity.get('order_id')
            payment_id = payment_entity.get('id')
            amount_paise = payment_entity.get('amount')
            if gateway_order_id and str(gateway_order_id).startswith('order_RKT'):
                store_service.confirm_online_payment(gateway_order_id, payment_id, amount_paise)
            elif notes.get('user_id') and notes.get('package_id'):
                from app.services.package_service import purchase_package
                purchase_package(int(notes['user_id']), int(notes['package_id']), payment_ref=payment_id)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500


'''


def block_bounds(lines, needle):
    start = None
    for i, ln in enumerate(lines):
        if needle in ln and ln.lstrip().startswith("@main.route"):
            start = i
            break
    if start is None:
        return None
    def_line = None
    for j in range(start + 1, min(start + 6, len(lines))):
        if lines[j].lstrip().startswith("def "):
            def_line = j
            break
    if def_line is None:
        return None
    end = len(lines)
    for k in range(def_line + 1, len(lines)):
        s = lines[k]
        if s.strip() == "":
            continue
        if not s[0].isspace():
            end = k
            break
    return start, end


def patch_check_session(src):
    marker = "E-COMMERCE: not-yet-activated members"
    if marker in src:
        return src, False
    pat = re.compile(
        r"(?P<i>[ \t]*)db_user = cur\.fetchone\(\)\n"
        r"[ \t]*if not db_user or not db_user\['is_active'\]:\n"
        r"[ \t]*logout_user\(\)\n"
        r"[ \t]*session\.clear\(\)\n"
        r"[ \t]*return jsonify\(\{\"success\": False, \"message\": \"Account deactivated\.\"\}\), 401"
    )
    m = pat.search(src)
    if not m:
        return src, False
    i = m.group("i")
    repl = "\n".join([
        i + "db_user = cur.fetchone()",
        i + "# " + marker + " stay logged in so they can",
        i + "# shop and activate. Admin deactivation still blocks MLM features.",
        i + "if not db_user:",
        i + "    logout_user()",
        i + "    session.clear()",
        i + '    return jsonify({"success": False, "message": "Account not found."}), 401',
        i + "is_active = bool(db_user['is_active'])",
    ])
    src = src[:m.start()] + repl + src[m.end():]

    old_ret = re.compile(
        r'return jsonify\(\{"success": True, "user": \{\n'
        r'[ \t]*"id": current_user\.id,\n'
        r'[ \t]*"email": current_user\.email,\n'
        r'[ \t]*"full_name": current_user\.full_name\n'
        r'[ \t]*\}\}\), 200'
    )
    m2 = old_ret.search(src)
    if m2:
        j = " " * 12
        repl2 = "\n".join([
            'return jsonify({"success": True, "user": {',
            j + '"id": current_user.id,',
            j + '"email": current_user.email,',
            j + '"full_name": current_user.full_name,',
            j + '"is_active": is_active',
            j + "}}), 200",
        ])
        src = src[:m2.start()] + repl2 + src[m2.end():]
    return src, True


AUTH_ME_PAT = re.compile(
    r"(?P<i>[ \t]*)# If user doesn't exist or is deactivated, kill their session immediately\n"
    r"[ \t]*if not db_user or not db_user\['is_active'\]:\n"
    r"[ \t]*logout_user\(\)\n"
    r"[ \t]*session\.clear\(\)\n"
    r'[ \t]*return jsonify\(\{"status": "error", "message": "Your account has been deactivated\."\}\), 401'
)


def patch_auth_me(src):
    if "E-COMMERCE: pre-activation members" in src:
        return src, False
    m = AUTH_ME_PAT.search(src)
    if not m:
        return src, False
    i = m.group("i")
    repl = "\n".join([
        i + "# E-COMMERCE: pre-activation members stay logged in so they can shop",
        i + "# and activate. is_active=False only means: no plan purchased yet.",
        i + "is_active = bool(db_user['is_active'])",
    ])
    src = src[:m.start()] + repl + src[m.end():]

    old_user = re.compile(
        r'"user": \{\n'
        r"([ \t]*)\"id\": current_user\.id,\n"
        r'[ \t]*"full_name": current_user\.full_name,\n'
        r'[ \t]*"email": current_user\.email,\n'
        r'[ \t]*"role_id": current_user\.role_id,'
    )
    m2 = old_user.search(src)
    if m2:
        j = m2.group(1)
        lines = [
            '"user": {',
            j + '"id": current_user.id,',
            j + '"full_name": current_user.full_name,',
            j + '"email": current_user.email,',
            j + '"role_id": current_user.role_id,',
            j + '"is_active": is_active,',
        ]
        src = src[:m2.start()] + "\n".join(lines) + src[m2.end():]
    return src, True


def patch_webhook(lines):
    src = "".join(lines)
    if "store_service.confirm_online_payment" in src:
        return lines, False
    b = block_bounds(lines, "'/webhook/payment'")
    if not b:
        return lines, False
    s, e = b
    lines[s:e] = [WEBHOOK_BLOCK]
    return lines, True


def patch_file(path, patchers):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    original = src
    for fn in patchers:
        src, ch = fn(src)
        if ch:
            print(f"  - {os.path.basename(path)}: {fn.__name__} applied")
    if src != original:
        shutil.copy(path, path + f".bak-{int(time.time())}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        return True
    return False


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "app/routes/main.py"
    if not os.path.exists(path):
        print(f"  ! {path} not found - skipped.")
        sys.exit(0)

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changed = False
    removed = []

    for needle in ['"/api/team/me"', '"/api/genealogy/me"']:
        b = block_bounds(lines, needle)
        if b is None:
            print(f'  - route {needle}: already absent')
            continue
        s, e = b
        n = sum(1 for x in lines[s:e] if x.strip())
        removed.append((s, e, n))
        for k in range(s, e):
            lines[k] = ""
        changed = True

    src = "".join(lines)
    src, ch = patch_check_session(src)
    if ch:
        lines = src.splitlines(keepends=True)
        changed = True
        print("  - check_session: pre-activation members may stay logged in")

    lines, ch = patch_webhook(lines)
    if ch:
        changed = True
        print("  - upgraded /webhook/payment to settle store orders")

    if changed:
        shutil.copy(path, path + f".bak-{int(time.time())}")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        for s, e, n in removed:
            print(f"  - removed duplicate route block ({n} code lines) near line {s+1}")
        print("  - backup written next to main.py as main.py.bak-*")
    else:
        print("  - main.py: nothing to change (already patched).")

    auth_path = os.path.join(os.path.dirname(path), "auth_routes.py")
    if os.path.exists(auth_path):
        patch_file(auth_path, [patch_auth_me])
    else:
        print("  - auth_routes.py not found next to main.py - skipped")


if __name__ == "__main__":
    main()
