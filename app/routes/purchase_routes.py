import hmac
import hashlib
import json
import logging
from flask import Blueprint, request, jsonify, session, current_app

# Existing imports
from app.services.package_service import purchase_package
from app.utils.auth import login_required

# Webhook activation import
# (Make sure you have this function in activation_service.py, or change it to match your logic)
from app.services.activation_service import activate_user_package 

logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# ==========================================
# EXISTING ROUTE (Wallet / E-Pin Purchase)
# ==========================================
@main.route("/purchase-package", methods=["POST"])
@login_required
def purchase_package_api():
    user_id = session["user_id"]

    data = request.json
    package_id = data.get("package_id")

    if not package_id:
        return jsonify({
            "success": False,
            "message": "Package ID required"
        }), 400

    result = purchase_package(user_id, package_id)

    return jsonify(result)

# ==========================================
# 🔥 NEW: PAYMENT GATEWAY WEBHOOK (Razorpay/Online)
# ==========================================
@main.route('/webhook/payment', methods=['POST'])
def payment_webhook():
    """
    This endpoint is called directly by the Payment Gateway (e.g., Razorpay) 
    when an online payment is genuinely successful.
    """
    # 1. Get the raw data and signature from the gateway
    payload = request.get_data(as_text=True)
    received_signature = request.headers.get('X-Razorpay-Signature')
    
    # SECURITY CHECK: If there is no signature, block it.
    if not received_signature:
        logger.warning("Webhook attack blocked: Missing signature.")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    try:
        # 2. Verify the Signature using your secret Gateway Key
        secret = current_app.config.get('PAYMENT_GATEWAY_SECRET', 'YOUR_TEST_SECRET_KEY')
        
        expected_signature = hmac.new(
            bytes(secret, 'utf-8'), 
            msg=bytes(payload, 'utf-8'), 
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, received_signature):
            logger.error("Webhook attack blocked: Invalid signature.")
            return jsonify({"status": "error", "message": "Invalid Signature"}), 400

        # 3. If signature matches, process the real data
        data = json.loads(payload)
        event_type = data.get('event')

        if event_type == 'payment.captured' or event_type == 'order.paid':
            payment_entity = data['payload']['payment']['entity']
            
            # Extract notes you passed when creating the order
            user_id = payment_entity['notes']['user_id']
            package_id = payment_entity['notes']['package_id']
            amount_paid = payment_entity['amount'] / 100  # Convert paise to rupees
            
            logger.info(f"Legit payment received: ₹{amount_paid} from User {user_id}")
            
            # 4. Trigger the activation & commission engine
            activate_user_package(user_id=user_id, package_id=package_id, payment_method="ONLINE")
            
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500
