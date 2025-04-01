from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_apscheduler import APScheduler

db = SQLAlchemy()
migrate = Migrate()
scheduler = APScheduler()  # Create an APScheduler instance


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.secret_key = app.config["SECRET_KEY"]

    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize APScheduler with persistent job store
    scheduler.init_app(app)
    scheduler.start()

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

    return app
