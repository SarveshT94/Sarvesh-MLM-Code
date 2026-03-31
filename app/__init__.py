import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_cors import CORS

# Login manager global
login_manager = LoginManager()


def create_app():

    app = Flask(__name__)

    # -----------------------------
    # CONFIG
    # -----------------------------
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")

    # -----------------------------
    # CORS ENABLE
    # -----------------------------
    CORS(
        app,
        resources={r"/api/*": {"origins": "http://localhost:3000"}},
        supports_credentials=True
    )

    # -----------------------------
    # IMPORT BLUEPRINTS
    # -----------------------------
    from app.routes.auth import auth_bp
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

    # -----------------------------
    # REGISTER BLUEPRINTS
    # -----------------------------
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    # 👤 USER / MAIN
    app.register_blueprint(main, url_prefix="/api")

    # 🧑‍💼 ADMIN CORE
    app.register_blueprint(admin, url_prefix="/api/admin")

    # 🌳 MLM TREE
    app.register_blueprint(admin_tree_bp, url_prefix="/api/admin/tree")

    # 💰 WALLET
    app.register_blueprint(admin_wallet_bp, url_prefix="/api/admin/wallet")

    # 💸 COMMISSION
    app.register_blueprint(admin_commission_bp, url_prefix="/api/admin/commission")

    # 🚨 FRAUD
    app.register_blueprint(admin_fraud_bp, url_prefix="/api/admin/fraud")

    # 📜 ACTIVITY LOGS
    app.register_blueprint(admin_activity_bp, url_prefix="/api/admin/activity")

    # ⏰ CRON
    app.register_blueprint(admin_cron_bp, url_prefix="/api/admin/cron")

    # 📊 ANALYTICS
    app.register_blueprint(admin_analytics_bp, url_prefix="/api/admin/analytics")

    # 🔔 NOTIFICATIONS
    app.register_blueprint(notification_bp, url_prefix="/api/notifications")

    # 🎫 SUPPORT (USER)
    app.register_blueprint(support_bp, url_prefix="/api/support")

    # 🎫 SUPPORT (ADMIN)
    app.register_blueprint(admin_support_bp, url_prefix="/api/admin/support")

    # 💾 BACKUPS
    app.register_blueprint(admin_backup_bp, url_prefix="/api/admin/backup")
    # -----------------------------
    # LOGIN MANAGER SETUP
    # -----------------------------
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from app.services.user_service import get_user_by_id
        user_data = get_user_by_id(user_id)
        if user_data:
            from app.routes.auth import User
            return User(user_data)
        return None

    # -----------------------------
    # ERROR HANDLERS
    # -----------------------------
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html"), 500

    return app
