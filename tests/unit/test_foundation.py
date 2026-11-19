import os
import re
import glob
from datetime import datetime, timezone
import pytest
from app.utils.security import hash_password, verify_password
from app.utils.formatting import format_rupiah, format_datetime
from app.utils.validators import (
    validate_email,
    validate_password,
    validate_string,
    validate_phone,
    validate_object_id,
    validate_int,
    ValidationError,
)
from app.models.schemas import COLLECTIONS


def test_argon2id_hashing():
    pwd = "AdminSecure123!"
    h = hash_password(pwd)
    assert h.startswith("$argon2id$")
    assert verify_password(h, pwd) is True
    assert verify_password(h, "WrongPassword123!") is False


def test_formatting_rupiah():
    assert format_rupiah(0) == "Rp 0"
    assert format_rupiah(3500) == "Rp 3.500"
    assert format_rupiah(58000) == "Rp 58.000"
    assert format_rupiah(12450000) == "Rp 12.450.000"


def test_format_datetime_uses_jakarta_timezone():
    utc_datetime = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert format_datetime(utc_datetime) == "01 Jan 2024, 07:00"


def test_validators():
    # Email
    assert validate_email("  Test@Example.COM  ") == "test@example.com"
    with pytest.raises(ValidationError):
        validate_email("invalid-email")
    with pytest.raises(ValidationError):
        validate_email({"$ne": ""})  # NoSQL injection injection probe

    # Password
    assert validate_password("Pass1234") == "Pass1234"
    with pytest.raises(ValidationError):
        validate_password("short7")
    with pytest.raises(ValidationError):
        validate_password("alllettersonly")
    with pytest.raises(ValidationError):
        validate_password("12345678")

    # Phone
    assert validate_phone("081234567890") == "081234567890"
    assert validate_phone("+6281234567890") == "+6281234567890"
    assert validate_phone("") is None
    with pytest.raises(ValidationError):
        validate_phone("12345")

    # Int
    assert validate_int("10", min_val=1, max_val=99) == 10
    with pytest.raises(ValidationError):
        validate_int("abc")
    with pytest.raises(ValidationError):
        validate_int(0, min_val=1)
    with pytest.raises(ValidationError):
        validate_int({"$gt": 0})


def test_eleven_collections_schema():
    """Tepat 11 koleksi tanpa koleksi ke-12 (Bab 12)."""
    expected = {
        "users", "categories", "master_product", "carts", "orders",
        "stock_movements", "promotions", "wishlists", "reviews",
        "notifications", "audit_logs"
    }
    assert set(COLLECTIONS.keys()) == expected
    assert len(COLLECTIONS) == 11


def test_six_layer_architecture_pymongo_isolation():
    """Hanya app/repositories yang boleh meng-import pymongo (Bab 8 & 18)."""
    disallowed_dirs = ["app/routes", "app/services", "app/utils"]
    pymongo_pattern = re.compile(r"^\s*(from|import)\s+pymongo", re.MULTILINE)

    for d in disallowed_dirs:
        py_files = glob.glob(f"{d}/**/*.py", recursive=True)
        for fpath in py_files:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                matches = pymongo_pattern.findall(content)
                assert not matches, f"Pelanggaran arsitektur: {fpath} meng-import pymongo!"

