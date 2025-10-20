# app.py
from flask import Flask, render_template, current_app, url_for
from flask_migrate import Migrate
from pathlib import Path
from flask_login import LoginManager
from config import get_config
from utilities.database import db, Item, User, ItemCheckout, ActivityLog
from auth import auth_bp
from inventory import inventory_bp
from checkout import checkout_bp
from main import main_bp
from contacts import contacts_bp
from properties import properties_bp
from smartlocks import smartlocks_bp
from exports import exports_bp

migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = "auth.login"  # Redirect to login page if not logged in


def create_app():
    app = Flask(__name__)

    # 1) Load config for the selected environment
    app.config.from_object(get_config())

    # 2) SQLite path hardening: ensure absolute, writable path BEFORE init_app
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite:///"):
        base_dir = Path.home() / "KBM2_data"  # per-user writable folder
        base_dir.mkdir(parents=True, exist_ok=True)
        raw_path = uri.replace("sqlite:///", "", 1).strip()
        filename = Path(raw_path).name if raw_path else "app.db"
        db_path = (base_dir / filename).resolve()
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"
        print("Using SQLite DB at:", app.config["SQLALCHEMY_DATABASE_URI"])

    # 3) Init DB & migrations NOW that URI is final
    db.init_app(app)
    migrate.init_app(app, db)

    # 4) Optional dev-only schema bootstrap
    if app.config.get("AUTO_CREATE_SCHEMA"):
        with app.app_context():
            db.create_all()

    # 5) Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(main_bp)  # '/' home
    app.register_blueprint(contacts_bp, url_prefix="/contacts")
    app.register_blueprint(properties_bp, url_prefix="/properties")
    app.register_blueprint(smartlocks_bp, url_prefix="/smart-locks")
    app.register_blueprint(exports_bp, url_prefix="/exports")

    # 6) Debug helpers (development convenience)
    if app.config.get("DEBUG"):
        @app.get("/debug/create_admin")
        def debug_create_admin():
            existing = User.query.filter_by(role="admin").first()
            if existing:
                return {"status": "exists", "user": existing.name}
            u = User(name="admin", email="devin@vestasells.com", role="admin")
            u.set_pin("1234")
            db.session.add(u)
            db.session.commit()
            return {"status": "created", "user": u.name}

        @app.get("/debug/items")
        def debug_items():
            items = Item.query.all()
            return {"count": len(items), "items": [item.to_dict() for item in items]}

    # 7) Health check
    @app.get("/health")
    def health():
        return {"ok": True}, 200

    # 8) Login manager
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # 9) Error handlers
    @app.errorhandler(500)
    def handle_500(error):
        return render_template("500.html"), 500

    # 10) Context processors (make helpers available in all templates)
    @app.context_processor
    def inject_template_helpers():
        def has_endpoint(name: str) -> bool:
            return name in current_app.view_functions

        def safe_url(endpoint: str, **kwargs) -> str:
            # Return a real URL if the endpoint exists, else '#'
            return url_for(endpoint, **kwargs) if has_endpoint(endpoint) else "#"

        return dict(has_endpoint=has_endpoint, safe_url=safe_url)

    return app


# For `flask --app app run`, having create_app is enough.
# You can optionally expose a concrete app instance too:
# app = create_app()
