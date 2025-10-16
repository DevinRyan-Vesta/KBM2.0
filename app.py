# app.py
from flask import Flask
from flask_migrate import Migrate
from pathlib import Path

from config import get_config
from utilities.database import db, Item
from auth.views import auth_bp
from inventory.views import inventory_bp
from checkout.views import checkout_bp

migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # ✅ Load config based on environment (defaults to "development")
    app.config.from_object(get_config())

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        db.create_all()
    
        @app.route("/debug/items")
        def debug_items():
            items = Item.query.all()
            return {"count": len(items), "items": [item.to_dict() for item in items]}

# --- SQLite path hardening: always use a writable absolute path ---
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")

    if uri.startswith("sqlite:///"):
        # Prefer a per-user folder to avoid permission issues
        base_dir = Path.home() / "KBM2_data"
        base_dir.mkdir(parents=True, exist_ok=True)

        # If your .env has a filename (e.g., sqlite:///data/app.db), keep the filename
        # Otherwise default to app.db
        raw_path = uri.replace("sqlite:///", "", 1).strip()
        filename = Path(raw_path).name if raw_path else "app.db"

        db_path = (base_dir / filename).resolve()
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"

        # Helpful debug line so we SEE the final DB path in the console
        print("Using SQLite DB at:", app.config["SQLALCHEMY_DATABASE_URI"])
# -----------------------------------------------------------------

    # Register blueprints...
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")

    @app.get("/health")
    def health():
        return {"ok": True}, 200

    return app

app = create_app()
