import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    """Konfigurasi aplikasi dari environment variables.
    Wajib fail-fast jika variabel wajib (SECRET_KEY, MONGO_URI) tidak diset (Bab 16).
    """
    SECRET_KEY = os.environ["SECRET_KEY"]
    MONGO_URI = os.environ["MONGO_URI"]
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "retailbrain")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    SESSION_LIFETIME_MINUTES = int(os.environ.get("SESSION_LIFETIME_MINUTES", "120"))
    ADMIN_SESSION_LIFETIME_MINUTES = int(os.environ.get("ADMIN_SESSION_LIFETIME_MINUTES", "30"))

    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "2"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    _upload_env = os.environ.get("UPLOAD_DIR", "instance/uploads")
    UPLOAD_DIR = _upload_env if os.path.isabs(_upload_env) else os.path.join(BASE_DIR, _upload_env)

    DELIVERY_FEE = int(os.environ.get("DELIVERY_FEE", "10000"))
    ALLOW_ADMIN_BOOTSTRAP = os.environ.get("ALLOW_ADMIN_BOOTSTRAP", "true").lower() == "true"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", None)


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    MONGO_DB_NAME = "retailbrain_test"
    RATELIMIT_ENABLED = False

