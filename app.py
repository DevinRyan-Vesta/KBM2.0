from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from auth.views import auth_bp
from inventory.views import inventory_bp
from checkout.views import checkout_bp
from utilities.database import init_db, db
from flask_migrate import Migrate
import config

# Configuration
db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=config['SECRET_KEY'],
        SQLALCHEMY_DATABASE_URI=config['DATABASE_URL'],
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

    # Initialize database and migration tool
    init_db(app)
    migrate.init_app(app, db)

    #Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(checkout_bp, url_prefix='/checkout')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)