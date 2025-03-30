from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.secret_key = app.config["SECRET_KEY"]

    # Register authentication blueprint
    from .auth import auth_bp

    app.register_blueprint(auth_bp)

    # Register API blueprint
    from .api import api_bp

    app.register_blueprint(api_bp)

    # Future: register other blueprints for products, scheduler, etc.

    return app
