# app_multitenant.py - Multi-tenant version of the application
from flask import Flask, render_template, current_app, url_for, g, redirect
from flask_migrate import Migrate
from pathlib import Path
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from config import get_config
import os
# Limiter lives in utilities/extensions.py so blueprints can import it
# without creating a circular import back to this module.
from utilities.extensions import limiter

# Master database (accounts, users)
from utilities.master_database import master_db, MasterUser

# Tenant database models (for schema creation)
from utilities.database import db

# Tenant manager and middleware
from utilities.tenant_manager import tenant_manager
from middleware.tenant_middleware import tenant_middleware

# Blueprints
from auth.views_multitenant import auth_bp
from accounts import accounts_bp
from app_admin import app_admin_bp
from inventory import inventory_bp
from checkout import checkout_bp
from main import main_bp
from contacts import contacts_bp
from properties import properties_bp
from audits import audits_bp
from smartlocks import smartlocks_bp
from exports import exports_bp
from search import search_bp
from settings import settings_bp

migrate_master = Migrate()
migrate_tenant = Migrate()

login_manager = LoginManager()
login_manager.login_view = "auth.login"

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # 1) Load config
    app.config.from_object(get_config())

    # Session idle timeout. Sessions are marked permanent on login (see
    # auth.views_multitenant), and Flask's SESSION_REFRESH_EACH_REQUEST is
    # True by default — together that gives us sliding-window idle timeout:
    # the cookie's expiry is reset on every request, so active users never
    # get bumped while idle ones do.
    #
    # Default 30 minutes. Override via PERMANENT_SESSION_LIFETIME env var
    # (in seconds) to make it longer/shorter per deployment.
    try:
        app.config["PERMANENT_SESSION_LIFETIME"] = int(os.getenv("PERMANENT_SESSION_LIFETIME", "1800"))
    except ValueError:
        app.config["PERMANENT_SESSION_LIFETIME"] = 1800
    app.config.setdefault("SESSION_REFRESH_EACH_REQUEST", True)

    # 2) Set up master database path (use Docker volume mount)
    master_base_dir = Path("master_db")
    master_base_dir.mkdir(parents=True, exist_ok=True)
    master_db_path = (master_base_dir / "master.db").resolve()
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{master_db_path.as_posix()}"
    print("Using Master DB at:", app.config["SQLALCHEMY_DATABASE_URI"])

    # 3) Initialize master database
    master_db.init_app(app)
    migrate_master.init_app(app, master_db, directory="migrations_master")

    # 4) Initialize tenant manager
    tenant_manager.init_app(app)

    # 5) Initialize tenant middleware
    tenant_middleware.init_app(app)

    # 6) Create master database schema if needed
    if app.config.get("AUTO_CREATE_SCHEMA"):
        with app.app_context():
            master_db.create_all()
            print("Master database schema created")

    # 6a) Apply pending tenant DB schema upgrades. Idempotent: each upgrade
    # checks whether its column/table is already present and only acts if
    # missing. Safe to run on every boot. See utilities/tenant_schema.py.
    try:
        from utilities.tenant_schema import upgrade_all_tenant_dbs
        upgrade_all_tenant_dbs(app.config.get("TENANT_DATA_DIR", "tenant_dbs"))
    except Exception as e:
        # Don't crash startup on migration trouble — just log loudly so the
        # operator can fix it. The relevant column will be missing until then.
        print(f"WARNING: tenant DB schema upgrade failed: {e}")

    # 7) Register blueprints
    # Root domain blueprints (signup, app admin)
    app.register_blueprint(accounts_bp, url_prefix="/accounts")
    app.register_blueprint(app_admin_bp)

    # Authentication (works on both root and tenant domains)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    # Tenant-only blueprints (require subdomain)
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(main_bp)  # '/' home
    app.register_blueprint(contacts_bp, url_prefix="/contacts")
    app.register_blueprint(properties_bp, url_prefix="/properties")
    app.register_blueprint(smartlocks_bp, url_prefix="/smart-locks")
    app.register_blueprint(exports_bp, url_prefix="/exports")
    app.register_blueprint(audits_bp, url_prefix="/audits")
    app.register_blueprint(search_bp)
    app.register_blueprint(settings_bp, url_prefix="/settings")

    # 8) Debug helpers (DISABLED FOR SECURITY)
    # These routes are disabled for production security
    # Use create_admin.py script instead to create app admin users
    # Uncomment only for local development if needed
    #
    # if app.config.get("DEBUG"):
    #     @app.get("/debug/create-app-admin")
    #     def debug_create_app_admin():
    #         """Create a test app admin user - DEVELOPMENT ONLY"""
    #         existing = MasterUser.query.filter_by(role="app_admin", email="admin@kbm.local").first()
    #         if existing:
    #             return {"status": "exists", "user": existing.name, "email": existing.email}
    #
    #         admin = MasterUser(
    #             account_id=None,
    #             name="App Admin",
    #             email="admin@kbm.local",
    #             role="app_admin",
    #             is_active=True
    #         )
    #         admin.set_pin("admin123")
    #         master_db.session.add(admin)
    #         master_db.session.commit()
    #         return {
    #             "status": "created",
    #             "user": admin.name,
    #             "email": admin.email,
    #             "pin": "admin123"
    #         }
    #
    #     @app.get("/debug/info")
    #     def debug_info():
    #         """Show debug information - DEVELOPMENT ONLY"""
    #         tenant = tenant_manager.get_current_tenant()
    #         return {
    #             "host": os.environ.get('request.host', 'N/A'),
    #             "is_root_domain": g.get('is_root_domain', False),
    #             "subdomain": g.get('subdomain', None),
    #             "tenant": tenant.to_dict() if tenant else None,
    #         }

    # 9) Health check
    @app.get("/health")
    def health():
        return {"ok": True, "multi_tenant": True}, 200

    # 9a) Caddy on-demand TLS validation endpoint.
    # Caddy calls this before issuing a Let's Encrypt cert for a subdomain.
    # Returns 200 if the requested host maps to an active tenant (or is the
    # configured root domain), 404 otherwise. A shared secret prevents abuse
    # if the endpoint is ever exposed beyond the internal docker network.
    @app.get("/_internal/check-domain")
    def _check_domain():
        from utilities.master_database import Account
        from flask import request as _req

        expected_secret = os.getenv("INTERNAL_API_SECRET", "")
        provided = _req.args.get("secret", "") or _req.headers.get("X-Internal-Secret", "")
        if not expected_secret or provided != expected_secret:
            return {"ok": False, "reason": "unauthorized"}, 403

        domain = (_req.args.get("domain", "") or "").lower().strip()
        if not domain:
            return {"ok": False, "reason": "missing-domain"}, 400

        base = (os.getenv("BASE_DOMAIN", "") or "").lower().split(":")[0]
        if not base:
            return {"ok": False, "reason": "base-domain-not-configured"}, 500

        if domain == base:
            return {"ok": True, "kind": "root"}, 200

        suffix = f".{base}"
        if not domain.endswith(suffix):
            return {"ok": False, "reason": "wrong-base-domain"}, 404

        subdomain = domain[: -len(suffix)]
        if not subdomain or "." in subdomain:
            return {"ok": False, "reason": "invalid-subdomain"}, 404

        account = Account.query.filter_by(subdomain=subdomain).first()
        if not account or account.status != "active":
            return {"ok": False, "reason": "no-such-tenant"}, 404

        return {"ok": True, "kind": "tenant", "subdomain": subdomain}, 200

    # 10) Login manager
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return master_db.session.get(MasterUser, int(user_id))
        except Exception:
            return None

    # 10a) CSRF Protection
    # Tie token lifetime to the session, not Flask-WTF's default 1-hour cap.
    # Without this, a page that's been open for >1h will fail any POST with
    # "CSRF token expired" even though the user is still logged in. The
    # tokens are still per-session and signed, so this doesn't weaken the
    # protection — it just removes the redundant clock.
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)
    csrf.init_app(app)

    # 10b) Rate Limiting
    # Only enable if configured in environment
    if os.getenv('RATELIMIT_ENABLED', 'false').lower() in ('true', '1', 'yes'):
        limiter.init_app(app)

    # 11) Error handlers
    @app.errorhandler(404)
    def handle_404(error):
        # If app admin is on root domain and hits 404, redirect to dashboard
        if current_user.is_authenticated and getattr(current_user, 'role', '') == 'app_admin' and g.get('is_root_domain', False):
            return redirect(url_for('app_admin.dashboard'))
        return render_template("404.html", error=error), 404

    @app.errorhandler(403)
    def handle_403(error):
        return render_template("403.html", error=error), 403

    @app.errorhandler(500)
    def handle_500(error):
        return render_template("500.html", error=error), 500

    # 12) Context processors
    @app.context_processor
    def inject_template_helpers():
        def has_endpoint(name: str) -> bool:
            return name in current_app.view_functions

        def safe_url(endpoint: str, **kwargs) -> str:
            return url_for(endpoint, **kwargs) if has_endpoint(endpoint) else "#"

        # Inject tenant information into all templates
        tenant = tenant_manager.get_current_tenant()

        # Inject the tenant's settings (or None if we're not in a tenant
        # context — root admin pages, signup, etc.) Templates can use
        # `tenant_settings.receipt_header` etc. with safe `if` guards.
        tenant_settings = None
        if tenant is not None:
            try:
                from utilities.database import get_tenant_settings
                tenant_settings = get_tenant_settings()
            except Exception:
                tenant_settings = None

        return dict(
            has_endpoint=has_endpoint,
            safe_url=safe_url,
            tenant=tenant,
            tenant_settings=tenant_settings,
            is_root_domain=g.get('is_root_domain', False)
        )

    # 13) Root domain landing page
    @app.route('/')
    def index():
        """
        Landing page.
        - Root domain: Show signup/login
        - Tenant domain: Redirect to main.home
        """
        if g.get('is_root_domain', False):
            # Root domain - show landing/signup page
            return render_template('landing.html')
        else:
            # Tenant domain - show tenant home
            from main.views import home
            return home()

    return app


# Expose a concrete app instance for WSGI servers
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = app.config.get("DEBUG", False)
    app.run(host="0.0.0.0", port=port, debug=debug)
