import os
from flask import Flask, render_template, request, jsonify
from flask_login import LoginManager, UserMixin
from flask_cors import CORS

# -----------------------------------
# Global Extensions
# -----------------------------------
login_manager = LoginManager()

# Enterprise Safe User Wrapper for Flask-Login
# We define it here to prevent circular import crashes from the routes.
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.full_name = user_data.get('full_name')
        self.email = user_data.get('email')
        self.role_id = user_data.get('role_id')

def create_app():
    """Enterprise Application Factory"""
    app = Flask(__name__)

    # -----------------------------
    # 1. Configuration
    # -----------------------------
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")

    # -----------------------------
    # 2. CORS Enable (React/Vue Ready)
    # -----------------------------
    CORS(
        app,
        resources={r"/api/*": {"origins": "http://localhost:3000"}},
        supports_credentials=True
    )

    # -----------------------------
    # 3. Import Blueprints (Cleaned & Updated)
    # -----------------------------
    # Notice: We use auth_routes as established in Step 11
    from app.routes.auth_routes import auth_bp 
    from app.routes.main import main
    from app.routes.admin_routes import admin

    # Sub-modules
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
    # 4. Register Blueprints (Deduplicated)
    # -----------------------------
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(main, url_prefix="/api")
    
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

    # -----------------------------
    # 5. Login Manager Setup
    # -----------------------------
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        # Localized import prevents the app from crashing on startup
        from app.db import get_cursor
        
        with get_cursor() as cur:
            cur.execute("SELECT id, full_name, email, role_id FROM users WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
            
            if user_data:
                return User(user_data)
        return None

    # -----------------------------
    # 6. Smart Error Handlers
    # -----------------------------
    @app.errorhandler(404)
    def page_not_found(e):
        # If it's an API request, return JSON. Otherwise, return HTML template.
        if request.path.startswith('/api/'):
            return jsonify({"status": "error", "message": "API Endpoint Not Found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith('/api/'):
            return jsonify({"status": "error", "message": "Internal Server Error"}), 500
        return render_template("errors/500.html"), 500

    return app
