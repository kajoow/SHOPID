import logging
from flask import g, current_app
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient

logger = logging.getLogger(__name__)

csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"
)

mongo_client: MongoClient | None = None


def init_extensions(app):
    global mongo_client

    # Inisialisasi CSRF
    csrf.init_app(app)

    # Inisialisasi Limiter
    limiter.init_app(app)

    # Inisialisasi koneksi MongoDB
    mongo_uri = app.config["MONGO_URI"]
    db_name = app.config["MONGO_DB_NAME"]

    mongo_client = MongoClient(mongo_uri)

    # Deteksi replica set
    try:
        hello_res = mongo_client.admin.command("hello")
        is_repl_set = "setName" in hello_res
        app.config["IS_REPLICA_SET"] = is_repl_set
        if not is_repl_set:
            logger.warning(
                "PERINGATAN: MongoDB berjalan tanpa replica set! "
                "Transaksi multi-dokumen tidak aktif, fallback langkah kompensasi akan digunakan (Bab 13.3)."
            )
        else:
            logger.info(f"MongoDB terhubung ke replica set: {hello_res.get('setName')}")
    except Exception as e:
        logger.error(f"Gagal memeriksa status replica set MongoDB: {e}")
        app.config["IS_REPLICA_SET"] = False


def get_db():
    """Mengembalikan objek database MongoDB yang sedang aktif."""
    global mongo_client
    if mongo_client is None:
        mongo_uri = current_app.config["MONGO_URI"]
        mongo_client = MongoClient(mongo_uri)
    db_name = current_app.config["MONGO_DB_NAME"]
    return mongo_client[db_name]


def get_client() -> MongoClient:
    """Mengembalikan objek MongoClient untuk transaksi session."""
    global mongo_client
    if mongo_client is None:
        mongo_uri = current_app.config["MONGO_URI"]
        mongo_client = MongoClient(mongo_uri)
    return mongo_client

