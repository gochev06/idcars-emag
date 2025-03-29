from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Future: register blueprints for auth, products, scheduler, and API endpoints here
    # For example:
    # from .auth import auth_bp
    # app.register_blueprint(auth_bp)

    return app
