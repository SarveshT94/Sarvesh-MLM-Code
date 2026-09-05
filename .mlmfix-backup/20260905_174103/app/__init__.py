"""
app/__init__.py  —  REWRITE (drop-in replacement)

Application factory. Changes vs the old file:
  * Registers the NEW team drill blueprint (app/routes/team_routes.py).
  * Drives CORS origins and cookie flags from config (no hard-coded
    localhost / SameSite=None in dev).
  * Registers a /healthz liveness endpoint.
  * No debug server here — production runs under gunicorn (see deploy/).

IMPORTANT HOUSEKEEPING (do this when you replace files):
  * DELETE the duplicate factory at  app/routes/__init__.py
    (it defines a SECOND, conflicting create_app and even references an
     undefined `rank_bp` -> if anyone imports it, the app crashes).
  * The old duplicate routes /api/team/me and /api/genealogy/me lived in BOTH
    app/routes/main.py and app/routes/user_routes.py. Keep the user_routes
    versions and remove the two blocks from main.py (instructions in the
    audit report).
"""
import os
import logging

from dotenv import load_dotenv
from flask import Flask, jsonify

from flask_login import LoginManager, UserMixin
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_executor import Executor

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address,
                  default_limits=[os.getenv("RATELIMIT_DEFAULT", "300 per minute")])
executor = Executor()


class User(UserMixin):
    def __init__(self, data):
        self.id = str(data.get("id"))
        self.full_name = data.get("full_name")
        self.email = data.get("email")
        self.role_id = data.get("role_id")
        self.phone = data.get("phone")
        self.referral_code = data.get("referral_code")


def create_app():
    app = Flask(__name__)

    from app.config.config import get_config
    cfg = get_config()

    app.config["SECRET_KEY"] = cfg.SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = cfg.SESSION_COOKIE_SECURE
    app.config["PREFERRED_URL_SCHEME"] = "https"

    limiter.init_app(app)

    from app.cache import cache
    cache.init_app(app)

    executor.init_app(app)

    Talisman(
        app,
        force_https=cfg.ENV == "production",
        content_security_policy={
            "default-src": ["'self'"],
            "style-src": ["'self'", "'unsafe-inline'",
                          "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
            "font-src": ["'self'", "https://fonts.gstatic.com",
                         "https://cdn.jsdelivr.net", "data:"],
            "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
        },
    )

    CORS(
        app,
        supports_credentials=True,
        origins=cfg.CORS_ORIGINS,
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # ----- Blueprints -----
    from app.routes.auth_routes import auth_bp
    from app.routes.main import main
    from app.routes.admin_routes import admin
    from app.routes.user_routes import user_bp
    from app.routes.team_routes import team_bp          # NEW drill-down API
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
    from app.routes.admin.report_routes import admin_report_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_package_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(main)
    app.register_blueprint(user_bp, url_prefix="/api")
    app.register_blueprint(team_bp, url_prefix="/api")     # NEW
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
    app.register_blueprint(admin_report_bp, url_prefix="/api/admin/report")

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.db import get_cursor
            with get_cursor() as cur:
                cur.execute(
                    "SELECT id, full_name, email, phone, referral_code, role_id "
                    "FROM users WHERE id = %s",
                    (user_id,),
                )
                data = cur.fetchone()
            return User(data) if data else None
        except Exception as e:
            logger.error("user_loader error: %s", e)
            return None

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"}), 200

    @app.errorhandler(404)
    def not_found(e):
        from flask import request, render_template
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import request, render_template
        logger.error("500 error: %s", e)
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    # Start / stop the DB pool cleanly.
    @app.before_request
    def _ensure_pool():
        from app.db import init_db_pool
        init_db_pool()

    return app
