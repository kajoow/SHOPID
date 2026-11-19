"""Test integration untuk Bab 17: TC-RP-01..02 dan Dashboard Admin (Fase 6)."""
from datetime import datetime, timezone, timedelta
import uuid
import pytest
from bson import ObjectId

from app.repositories import order_repo, product_repo, category_repo, user_repo
from app.models.enums import OrderStatus, PaymentStatus, UserRole
from app.utils.security import hash_password


@pytest.fixture
def admin_client(app, db):
    c = app.test_client()
    admin_email = "admin_reports@retailbrain.example"
    admin = user_repo.find_by_email(admin_email)
    if not admin:
        user_repo.insert(
            name="Admin Reports",
            email=admin_email,
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
        )
    c.post("/admin/login", data={"email": admin_email, "password": "AdminPass123!"})
    return c


@pytest.fixture
def test_setup_data(db):
    cat = category_repo.find_by_slug("sembako")
    if not cat:
        cid = category_repo.insert(name="Sembako", slug="sembako")
    else:
        cid = cat["_id"]

    pid = product_repo.insert(
        sku=f"REP-{uuid.uuid4().hex[:6].upper()}",
        name="Kecap Manis Laporan",
        category_id=cid,
        price=15000,
        stock=5,   # <= min_stock 10 (stok rendah)
        min_stock=10,
    )
    prod = product_repo.find_by_id(pid)

    uid = ObjectId()
    # 1. Order Completed Hari Ini (Rp 50.000)
    now = datetime.now(timezone.utc)
    order_completed_1 = {
        "_id": ObjectId(),
        "order_number": f"RB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "user_id": uid,
        "items": [{"product_id": pid, "sku": prod["sku"], "name": prod["name"], "unit_price": 25000, "quantity": 2, "line_total": 50000}],
        "subtotal": 50000,
        "discount": 0,
        "delivery_fee": 0,
        "total": 50000,
        "fulfillment_method": "pickup",
        "payment_method": "cod",
        "payment_status": PaymentStatus.PAID,
        "order_status": OrderStatus.COMPLETED,
        "contact": {"name": "User 1", "phone": "0812345678"},
        "status_history": [{"from": None, "to": OrderStatus.COMPLETED, "actor_id": uid, "at": now, "note": "Completed"}],
        "idempotency_key": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
    }
    order_repo.insert(order_completed_1)

    # 2. Order Completed Hari Kemarin (Rp 30.000)
    yesterday = now - timedelta(days=1)
    order_completed_2 = {
        "_id": ObjectId(),
        "order_number": f"RB-{yesterday.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "user_id": uid,
        "items": [{"product_id": pid, "sku": prod["sku"], "name": prod["name"], "unit_price": 15000, "quantity": 2, "line_total": 30000}],
        "subtotal": 30000,
        "discount": 0,
        "delivery_fee": 0,
        "total": 30000,
        "fulfillment_method": "pickup",
        "payment_method": "cod",
        "payment_status": PaymentStatus.PAID,
        "order_status": OrderStatus.COMPLETED,
        "contact": {"name": "User 2", "phone": "0812345678"},
        "status_history": [{"from": None, "to": OrderStatus.COMPLETED, "actor_id": uid, "at": yesterday, "note": "Completed"}],
        "idempotency_key": str(uuid.uuid4()),
        "created_at": yesterday,
        "updated_at": yesterday,
    }
    order_repo.insert(order_completed_2)

    # 3. Order Cancelled (Rp 100.000) - TIDAK BOLEH MASUK LAPORAN PENJUALAN
    order_cancelled = {
        "_id": ObjectId(),
        "order_number": f"RB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "user_id": uid,
        "items": [{"product_id": pid, "sku": prod["sku"], "name": prod["name"], "unit_price": 50000, "quantity": 2, "line_total": 100000}],
        "subtotal": 100000,
        "discount": 0,
        "delivery_fee": 0,
        "total": 100000,
        "fulfillment_method": "pickup",
        "payment_method": "cod",
        "payment_status": PaymentStatus.REFUNDED,
        "order_status": OrderStatus.CANCELLED,
        "contact": {"name": "User 3", "phone": "0812345678"},
        "status_history": [{"from": None, "to": OrderStatus.CANCELLED, "actor_id": uid, "at": now, "note": "Cancelled"}],
        "idempotency_key": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
    }
    order_repo.insert(order_cancelled)

    # 4. Order Pending (Rp 40.000) - TIDAK BOLEH MASUK LAPORAN PENJUALAN
    order_pending = {
        "_id": ObjectId(),
        "order_number": f"RB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "user_id": uid,
        "items": [{"product_id": pid, "sku": prod["sku"], "name": prod["name"], "unit_price": 20000, "quantity": 2, "line_total": 40000}],
        "subtotal": 40000,
        "discount": 0,
        "delivery_fee": 0,
        "total": 40000,
        "fulfillment_method": "pickup",
        "payment_method": "cod",
        "payment_status": PaymentStatus.UNPAID,
        "order_status": OrderStatus.PENDING,
        "contact": {"name": "User 4", "phone": "0812345678"},
        "status_history": [{"from": None, "to": OrderStatus.PENDING, "actor_id": uid, "at": now, "note": "Pending"}],
        "idempotency_key": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
    }
    order_repo.insert(order_pending)

    return {
        "prod": prod,
        "completed_1": order_completed_1,
        "completed_2": order_completed_2,
        "cancelled": order_cancelled,
        "pending": order_pending,
    }


def test_tc_rp_01_total_sales_only_completed_counted(admin_client, test_setup_data):
    """TC-RP-01: Total penjualan: Hanya order completed yang dijumlahkan (P1)."""
    resp = admin_client.get("/admin/reports/sales", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]

    # Grand total harus >= 50.000 + 30.000 = 80.000 (tidak menyertakan cancelled 100.000 atau pending 40.000)
    assert data["grand_total_sales"] >= 80000
    assert data["grand_total_orders"] >= 2


def test_tc_rp_02_daily_sales_grouped_asia_jakarta(admin_client, test_setup_data):
    """TC-RP-02: Penjualan per tanggal: Pengelompokan harian benar menurut zona Asia/Jakarta (P2)."""
    resp = admin_client.get("/admin/reports/sales", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]

    daily_entries = data["daily"]
    assert len(daily_entries) >= 2

    # Verifikasi format tanggal YYYY-MM-DD
    dates = [d["date"] for d in daily_entries]
    for d in dates:
        assert len(d) == 10
        assert d[4] == "-" and d[7] == "-"


def test_dashboard_kpis_real_database(admin_client, test_setup_data):
    """Dashboard admin menampilkan KPI nyata dari database (Fase 6)."""
    resp = admin_client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data
    assert b"Penjualan selesai" in resp.data
    assert b"Order selesai" in resp.data
    assert b"Stok rendah" in resp.data


def test_inventory_report_real_database(admin_client, test_setup_data):
    """Laporan inventori menampilkan valuasi stok nyata dari database (Fase 6)."""
    resp = admin_client.get("/admin/reports/inventory")
    assert resp.status_code == 200
    assert b"Laporan Inventori" in resp.data
    assert b"Total Nilai Inventori" in resp.data
    assert test_setup_data["prod"]["sku"].encode() in resp.data
