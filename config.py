import os
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    EMAG_API_KEY = os.environ.get("EMAG_API_KEY")
    FITNESS1_API_KEY = os.environ.get("FITNESS1_API_KEY")
    NEW_EMAG_API_KEY = os.environ.get("NEW_EMAG_API_KEY")  # TODO: remove it for prod
    # Additional configuration options can be added here

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI ", "sqlite:///app.db"
    )

    # Flask app configuration
    FLASK_APP = os.environ.get("FLASK_APP", "app:create_app()")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # APScheduler configuration
    SCHEDULER_API_ENABLED = True
    APSCHEDULER_JOBSTORES = {
        "default": {"type": "sqlalchemy", "url": SQLALCHEMY_DATABASE_URI}
    }
    APSCHEDULER_TIMEZONE = "UTC"  # or set your local timezone
    APSCHEDULER_JOB_DEFAULTS = {"coalesce": False, "max_instances": 1}
