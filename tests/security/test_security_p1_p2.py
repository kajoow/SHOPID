"""Test keamanan dan otorisasi Bab 17: TC-RB-05..06, TC-PR-11, TC-SC-02, TC-SC-07..08."""
import os
import re
import uuid
import pytest
from bson import ObjectId

from app.repositories import user_repo, product_repo, category_repo, order_repo
from app.models.enums import UserRole, OrderStatus, PaymentStatus
from app.utils.security import hash_password


@pytest.fixture
def user_client(app, db):
    c = app.test_client()
    email = f"user_sec_{uuid.uuid4().hex[:4]}@example.com"
    user_repo.insert(
        name="User Security",
        email=email,
        password_hash=hash_password("SecPass123!"),
        role=UserRole.USER,
        phone="081234567891",
    )
    c.post("/auth/login", data={"email": email, "password": "SecPass123!"})
    return c


@pytest.fixture
def other_user_order(db):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    other_uid = ObjectId()
    oid = ObjectId()
    order_doc = {
        "_id": oid,
        "order_number": f"RB-20261116-{uuid.uuid4().hex[:6].upper()}",
        "user_id": other_uid,
        "items": [{"product_id": ObjectId(), "sku": "SEC-001", "name": "Item Sec", "unit_price": 10000, "quantity": 1, "line_total": 10000}],
        "subtotal": 10000,
        "discount": 0,
        "delivery_fee": 0,
        "total": 10000,
        "fulfillment_method": "pickup",
        "payment_method": "bank_transfer",
        "payment_status": PaymentStatus.UNPAID,
        "order_status": OrderStatus.PENDING,
        "contact": {"name": "Victim", "phone": "081299998888"},
        "status_history": [{"from": None, "to": OrderStatus.PENDING, "actor_id": other_uid, "at": now, "note": "Order"}],
        "idempotency_key": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
    }
    order_repo.insert(order_doc)
    return order_doc


def test_tc_rb_05_user_action_on_other_user_order_rejected(user_client, other_user_order):
    """TC-RB-05: User membatalkan atau mengunggah bukti ke order orang lain -> 404 (P1)."""
    oid = str(other_user_order["_id"])

    # 1. Coba batalkan order orang lain
    r_cancel = user_client.post(f"/orders/{oid}/cancel")
    assert r_cancel.status_code == 404

    # 2. Coba unggah bukti ke order orang lain
    import io
    fake_img = io.BytesIO(b"dummy")
    r_proof = user_client.post(f"/orders/{oid}/payment-proof", data={"proof": (fake_img, "p.jpg")}, content_type="multipart/form-data")
    assert r_proof.status_code == 404

    # Status order korban tidak boleh berubah
    order_after = order_repo.find_by_id(other_user_order["_id"])
    assert order_after["order_status"] == OrderStatus.PENDING


@pytest.mark.parametrize("route_path", [
    "/admin/dashboard",
    "/admin/products",
    "/admin/categories",
    "/admin/inventory",
    "/admin/inventory/movements",
    "/admin/orders",
    "/admin/payments",
    "/admin/reports/sales",
    "/admin/reports/inventory",
])
def test_tc_rb_06_all_admin_routes_forbidden_for_user(user_client, route_path):
    """TC-RB-06: Seluruh rute /admin/* wajib mengembalikan 403 Forbidden bagi role user (P1)."""
    resp = user_client.get(route_path)
    assert resp.status_code == 403


def test_tc_pr_11_nosql_injection_sanitization(user_client):
    """TC-PR-11: Upaya injeksi operator NoSQL pada pencarian disanitasi tanpa error atau manipulasi query (P1)."""
    # Kirim parameter bernilai operator atau ekspresi berbahaya
    resp = user_client.get("/products?q[$ne]=test")
    assert resp.status_code in [200, 400, 422]

    resp2 = user_client.get('/products?q={"$gt": ""}')
    assert resp2.status_code in [200, 400, 422]


def test_tc_sc_02_stored_xss_autoescaped(app, user_client, db):
    """TC-SC-02: Stored XSS: Tag script di-escape oleh Jinja2 dan tidak dieksekusi sebagai HTML (P1)."""
    xss_payload = "<script>alert(1)</script>"

    cat = category_repo.find_by_slug("sembako")
    cid = cat["_id"] if cat else category_repo.insert(name="Sembako", slug="sembako")

    pid = product_repo.insert(
        sku=f"XSS-{uuid.uuid4().hex[:4].upper()}",
        name=f"Kecap XSS {xss_payload}",
        category_id=cid,
        price=10000,
        stock=10,
    )

    resp = user_client.get(f"/products/{pid}")
    assert resp.status_code == 200
    # Harus di-escape menjadi &lt;script&gt;
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in resp.data
    # Tidak boleh muncul raw unescaped script tag dalam konteks executable HTML
    assert b"<script>alert(1)</script>" not in resp.data


def test_tc_sc_07_error_handler_no_stack_trace(client):
    """TC-SC-07: Error handler menyembunyikan stack trace / traceback dari pengguna (P1)."""
    # Akses ObjectId tidak valid yang menghasilkan 404
    resp = client.get("/products/invalid-object-id-123")
    assert resp.status_code == 404
    assert b"Traceback" not in resp.data
    assert b"File \"" not in resp.data


def test_tc_sc_08_no_real_secrets_in_repo():
    """TC-SC-08: Tidak ada rahasia atau MONGO_URI dengan password asli yang ter-hardcode (P1)."""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    pattern = re.compile(r"mongodb(\+srv)?://[^:\s]+:[^@\s]+@")
    for root, dirs, files in os.walk(root_dir):
        if ".git" in dirs:
            dirs.remove(".git")
        if ".venv" in dirs:
            dirs.remove(".venv")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        for fname in files:
            if fname.endswith((".py", ".json", ".md", ".env.example")):
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    matches = pattern.findall(content)
                    assert len(matches) == 0, f"Ditemukan connection string dengan credential di {fpath}"
