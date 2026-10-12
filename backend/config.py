"""
config.py
Reads every setting from environment variables (loaded from .env in
development). Nothing secret is ever written in code.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask signs the session cookie with this. Must be long and random in
    # production: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # PostgreSQL connection string, e.g.
    #   postgresql://postgres:password@localhost:5432/birthday_wall
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/birthday_wall")
    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

    # MongoDB. If MONGO_URI is empty the app still runs; logs are skipped and
    # reactions / wall settings return 503.
    MONGO_URI = os.getenv("MONGO_URI", "")
    MONGO_DB = os.getenv("MONGO_DB", "birthday_wall")

    # Cloudinary, in the single-URL form shown on the Cloudinary dashboard:
    #   cloudinary://API_KEY:API_SECRET@CLOUD_NAME
    # If empty, text-only wishes still work but file uploads return 503.
    CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")

    # Default timezone for birthdays when the organizer does not send one.
    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")

    # Reject any request body over 120 MB before reading it
    # (5 files, the biggest being a 50 MB video).
    MAX_CONTENT_LENGTH = 120 * 1024 * 1024

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True              # JavaScript cannot read it
    SESSION_COOKIE_SAMESITE = "Lax"             # basic CSRF protection
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV") == "production"  # HTTPS only in prod

    # Upload rules. These mirror the CHECK constraints in the database; the
    # database is the final authority, these just fail faster with nicer
    # messages before a file is sent to Cloudinary.
    MAX_FILES_PER_WISH = 5
    MAX_FILE_BYTES = {
        "image": 10 * 1024 * 1024,
        "audio": 20 * 1024 * 1024,
        "video": 50 * 1024 * 1024,
    }
    ALLOWED_MIME_TYPES = {
        "image": {"image/jpeg", "image/png", "image/gif", "image/webp", "image/heic"},
        "audio": {"audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg", "audio/wav", "audio/x-m4a"},
        "video": {"video/mp4", "video/webm", "video/quicktime"},
    }
