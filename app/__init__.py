import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.extensions import scheduler as sc

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.secret_key = app.config["SECRET_KEY"]
    app.debug = app.config["DEBUG"]

    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize APScheduler with persistent job store
    sc.init_app(app)
    sc.start()

    # Register authentication blueprint
    from .auth import auth_bp

    app.register_blueprint(auth_bp)

    # Register API blueprint
    from .api import api_bp

    app.register_blueprint(api_bp)

    from .scheduler import sched_bp

    app.register_blueprint(sched_bp, url_prefix="/scheduler")

    with app.app_context():
        db.create_all()  # For development; in production use migrations

    # if not app.debug:
    #     file_handler = RotatingFileHandler(
    #         "logs/app.log", maxBytes=10240, backupCount=10
    #     )
    #     file_handler.setFormatter(
    #         logging.Formatter(
    #             "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    #         )
    #     )
    #     file_handler.setLevel(logging.INFO)
    #     app.logger.addHandler(file_handler)
    #     app.logger.setLevel(logging.INFO)
    #     app.logger.info("App startup")

    return app
