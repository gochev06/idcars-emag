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
    # SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
