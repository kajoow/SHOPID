import pytest
from app import create_app
from app.config import Config


class SecurityTestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = True  # Aktifkan CSRF untuk pengujian
    MONGO_DB_NAME = "retailbrain_test"
    RATELIMIT_ENABLED = False


def test_tc_sc_01_csrf_protection_rejects_unprotected_post():
    """TC-SC-01: CSRF POST tanpa token ditolak dengan status 403 (P1)."""
    app = create_app(SecurityTestConfig)
    client = app.test_client()

    resp = client.post("/auth/login", data={"email": "budi@example.com", "password": "Password123!"})
    assert resp.status_code == 403


def test_tc_sc_03_security_headers(client):
    """TC-SC-03: Security headers (CSP, nosniff, X-Frame-Options) ada di respons (P2)."""
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in resp.headers
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]

