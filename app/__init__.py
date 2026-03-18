import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name=None):
    app = Flask(__name__)

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    from app.config.settings import config_map

    app.config.from_object(config_map.get(config_name, config_map["development"]))

    # Logging
    logging.basicConfig(
        level=logging.DEBUG if app.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Proxy fix for Cloudflare Tunnel / reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # User loader
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.purchases import purchases_bp
    from app.routes.budget import budget_bp
    from app.routes.documents import documents_bp
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(purchases_bp)
    app.register_blueprint(budget_bp, url_prefix="/budget")
    app.register_blueprint(documents_bp, url_prefix="/documents")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Register CLI commands
    from app.cli import register_cli

    register_cli(app)

    # Template context
    from app.services.fiscal_year import get_current_fiscal_year_label
    from flask_login import current_user

    @app.context_processor
    def inject_globals():
        ctx = {
            "current_fiscal_year_label": get_current_fiscal_year_label(),
        }
        if current_user.is_authenticated and current_user.is_global_admin:
            from app.services.department import get_active_departments
            ctx["all_departments"] = get_active_departments()
        return ctx

    # Error handlers
    from app.routes.errors import register_error_handlers

    register_error_handlers(app)

    return app
