# -----------------------------------
# 1. Standard Library
# -----------------------------------
import os
import logging

# -----------------------------------
# 2. Environment
# -----------------------------------
from dotenv import load_dotenv

# 🔥 Load .env FIRST (VERY IMPORTANT)
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# -----------------------------------
# 3. Flask Core
# -----------------------------------
from flask import Flask, render_template, request, jsonify

# -----------------------------------
# 4. Flask Extensions
# -----------------------------------
from flask_login import LoginManager, UserMixin
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

# -----------------------------------
# Logging Configuration
# -----------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

# -----------------------------------
# Global Extensions (IMPORTANT)
# -----------------------------------
login_manager = LoginManager()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# -----------------------------------
# Enterprise User Wrapper
# -----------------------------------
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data.get('id'))
        self.full_name = user_data.get('full_name')
        self.email = user_data.get('email')
        self.role_id = user_data.get('role_id')
        self.phone = user_data.get('phone')
        self.referral_code = user_data.get('referral_code')

# -----------------------------------
# Application Factory
# -----------------------------------
def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

    if not app.config["SECRET_KEY"]:
        raise ValueError("SECRET_KEY is not set in environment variables")

    limiter.init_app(app)

    csp = {
        'default-src': ['\'self\''],
        'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net', 'https://fonts.googleapis.com'],
        'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdn.jsdelivr.net', 'data:'],
        'script-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net']
    }
    Talisman(app, content_security_policy=csp)

    # =======================================================
    # 🔥 BULLETPROOF CORS CONFIGURATION
    # This completely opens the bridge between Next.js and Flask
    # =======================================================
    CORS(
        app,
        supports_credentials=True,
        origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"]
    )

    # Register Blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.main import main
    from app.routes.admin_routes import admin
    from app.routes.admin.tree_routes import admin_tree_bp
    from app.routes.admin.wallet_routes import admin_wallet_bp
    from app.routes.admin.commission_routes import admin_commission_bp
    from app.routes.admin.fraud_routes import admin_fraud_bp
    from app.routes.admin.activity_routes import admin_activity_bp
    from app.routes.admin.cron_routes import admin_cron_bp
    from app.routes.admin.analytics_routes import admin_analytics_bp
    from app.routes.notification_routes import notification_bp
    from app.routes.support_routes import support_bp
    from app.routes.admin.support_routes import admin_support_bp
    from app.routes.admin.backup_routes import admin_backup_bp
    from app.routes.admin.package_routes import admin_package_bp
    from app.routes.profile_routes import profile_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_package_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix="/api/admin")
    app.register_blueprint(admin_tree_bp, url_prefix="/api/admin/tree")
    app.register_blueprint(admin_wallet_bp, url_prefix="/api/admin/wallet")
    app.register_blueprint(admin_commission_bp, url_prefix="/api/admin/commission")
    app.register_blueprint(admin_fraud_bp, url_prefix="/api/admin/fraud")
    app.register_blueprint(admin_activity_bp, url_prefix="/api/admin/activity")
    app.register_blueprint(admin_cron_bp, url_prefix="/api/admin/cron")
    app.register_blueprint(admin_analytics_bp, url_prefix="/api/admin/analytics")
    app.register_blueprint(notification_bp, url_prefix="/api/notifications")
    app.register_blueprint(support_bp, url_prefix="/api/support")
    app.register_blueprint(admin_support_bp, url_prefix="/api/admin/support")
    app.register_blueprint(admin_backup_bp, url_prefix="/api/admin/backup")

    # Login Manager
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.db import get_cursor

            with get_cursor() as cur:
                cur.execute(
                    "SELECT id, full_name, email, phone, referral_code, role_id FROM users WHERE id = %s",
                    (user_id,)
                )
                user_data = cur.fetchone()

                if user_data:
                    return User(user_data)

        except Exception as e:
            logger.error(f"user_loader error: {str(e)}")

        return None

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({"status": "error", "message": "API Endpoint Not Found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"500 error: {str(e)}")
        if request.path.startswith('/api/'):
            return jsonify({"status": "error", "message": "Internal Server Error"}), 500
        return render_template("errors/500.html"), 500

    return app
