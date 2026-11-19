import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

# Pastikan default minimal untuk testing jika belum ada di env
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-execution-only-12345")
os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27017/?replicaSet=rs0&directConnection=true")
os.environ.setdefault("MONGO_DB_NAME", "retailbrain_test")

import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import get_client, get_db


@pytest.fixture(scope="session")
def app():
    # Gunakan database terpisah untuk testing
    test_app = create_app(TestConfig)
    with test_app.app_context():
        # Bersihkan database test sebelum menjalankan test suite
        client = get_client()
        client.drop_database(TestConfig.MONGO_DB_NAME)
        # Jalankan runner CLI init-db
        from app.commands import init_db_command
        runner = test_app.test_cli_runner()
        runner.invoke(init_db_command)
        yield test_app
        # Bersihkan setelah selesai
        client.drop_database(TestConfig.MONGO_DB_NAME)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        return get_db()
