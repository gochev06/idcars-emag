from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.secret_key = app.config["SECRET_KEY"]

    db.init_app(app)
    migrate.init_app(app, db)

    # Register authentication blueprint
    from .auth import auth_bp

    app.register_blueprint(auth_bp)

    # Register API blueprint
    from .api import api_bp

    app.register_blueprint(api_bp)

    # Future: register other blueprints for products, scheduler, etc.

    with app.app_context():
        db.create_all()  # For development; in production use migrations

    return app
