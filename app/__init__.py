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
        if app.config.get("FLASK_ENV") == "development":
            db.create_all()

            # Optionally populate the database if it's empty.
            from initialize import populate_fitness_categories, populate_mappings

            populate_fitness_categories()
            populate_mappings()

    return app
