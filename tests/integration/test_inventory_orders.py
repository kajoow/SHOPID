"""Test integration untuk Bab 17: TC-IN-01..05 dan TC-OR-01..15 serta TC-SC-06."""
import io
import uuid
from datetime import datetime, timezone
import pytest
from bson import ObjectId
from PIL import Image

from app.repositories import (
    product_repo,
    category_repo,
    stock_repo,
    user_repo,
    order_repo,
    promotion_repo,
)
from app.models.enums import (
    UserRole,
    OrderStatus,
    PaymentStatus,
    FulfillmentMethod,
    PaymentMethod,
    StockMovementType,
    StockReferenceType,
    DiscountType,
)
from app.utils.security import hash_password


@pytest.fixture
def admin_client(app, db):
    c = app.test_client()
    admin_email = "admin_orders_inv@retailbrain.example"
    admin = user_repo.find_by_email(admin_email)
    if not admin:
        admin_id = user_repo.insert(
            name="Admin OrderInv",
            email=admin_email,
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
        )
    c.post("/admin/login", data={"email": admin_email, "password": "AdminPass123!"})
    return c


@pytest.fixture
def user_client(app, db):
    c = app.test_client()
    user_email = "user_orders_inv@example.com"
    user = user_repo.find_by_email(user_email)
    if not user:
        user_id = user_repo.insert(
            name="User OrderInv",
            email=user_email,
            password_hash=hash_password("UserPass123!"),
            role=UserRole.USER,
            phone="081234567899",
        )
    else:
        user_id = user["_id"]
    c.post("/auth/login", data={"email": user_email, "password": "UserPass123!"})
    return c, user_id


@pytest.fixture
def other_user_client(app, db):
    c = app.test_client()
    user_email = "other_user_inv@example.com"
    user = user_repo.find_by_email(user_email)
    if not user:
        user_id = user_repo.insert(
            name="Other User",
            email=user_email,
            password_hash=hash_password("UserPass123!"),
            role=UserRole.USER,
            phone="081299998888",
        )
    c.post("/auth/login", data={"email": user_email, "password": "UserPass123!"})
    return c


@pytest.fixture
def test_product(db):
    cat = category_repo.find_by_slug("sembako")
    if not cat:
        cid = category_repo.insert(name="Sembako", slug="sembako")
    else:
        cid = cat["_id"]

    sku = f"INV-TEST-{uuid.uuid4().hex[:6].upper()}"
    pid = product_repo.insert(
        sku=sku,
        name="Minyak Goreng Test",
        category_id=cid,
        price=20000,
        stock=50,
        min_stock=10,
    )
    return product_repo.find_by_id(pid)


def create_sample_image_file(format="JPEG", filename="proof.jpg"):
    file_bytes = io.BytesIO()
    img = Image.new("RGB", (200, 200), color=(73, 109, 137))
    img.save(file_bytes, format=format)
    file_bytes.seek(0)
    return file_bytes, filename


# ----------------------------------------------------------------------
# 1. TEST TC-IN (Inventori)
# ----------------------------------------------------------------------

def test_tc_in_01_stock_addition(admin_client, test_product):
    """TC-IN-01: Penambahan stok (addition 50) -> Stok +50, after = before + 50 (P1)."""
    pid = str(test_product["_id"])
    before_stock = test_product["stock"]

    resp = admin_client.post(
        f"/admin/inventory/{pid}/adjust",
        json={"type": "addition", "quantity": 50, "note": "Restock supplier"},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["after_stock"] == before_stock + 50

    updated = product_repo.find_by_id(test_product["_id"])
    assert updated["stock"] == before_stock + 50


def test_tc_in_02_stock_correction(admin_client, test_product):
    """TC-IN-02: Koreksi stok ke 30 dengan catatan -> record bertanda selisih, stok jadi 30 (P1)."""
    pid = str(test_product["_id"])
    before_stock = test_product["stock"]

    resp = admin_client.post(
        f"/admin/inventory/{pid}/adjust",
        json={"type": "correction", "new_stock": 30, "note": "Hasil stock opname fisik"},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["after_stock"] == 30
    assert data["quantity"] == 30 - before_stock

    updated = product_repo.find_by_id(test_product["_id"])
    assert updated["stock"] == 30


def test_tc_in_03_stock_correction_negative_rejected(admin_client, test_product):
    """TC-IN-03: Koreksi menghasilkan stok negatif -> 422 ditolak (P1)."""
    pid = str(test_product["_id"])

    resp = admin_client.post(
        f"/admin/inventory/{pid}/adjust",
        json={"type": "correction", "new_stock": -1, "note": "Opname salah"},
    )
    assert resp.status_code == 422


def test_adjust_stock_form_validation_error(admin_client, test_product):
    """Form HTML submit adjust stock dengan note < 3 karakter mengembalikan 422 dan render template inventory tanpa 500 error."""
    pid = str(test_product["_id"])
    resp = admin_client.post(
        f"/admin/inventory/{pid}/adjust",
        data={"type": "correction", "new_stock": "10", "note": "a"},
    )
    assert resp.status_code == 422
    assert b"Catatan koreksi minimal 3 karakter" in resp.data
    assert b"Manajemen Inventori" in resp.data


def test_tc_in_04_low_stock_detection(admin_client, test_product):
    """TC-IN-04: Deteksi low stock (stok 10 <= min_stock 10) -> tampil pada filter stok rendah (P2)."""
    pid = str(test_product["_id"])
    admin_client.post(
        f"/admin/inventory/{pid}/adjust",
        json={"type": "correction", "new_stock": 10, "note": "Set stok ke min_stock"},
    )

    resp = admin_client.get("/admin/inventory?low_stock=true")
    assert resp.status_code == 200
    assert test_product["sku"].encode() in resp.data


def test_tc_in_05_stock_invariants(db):
    """TC-IN-05: Seluruh record stock_movements wajib mematuhi after = before + quantity (P1)."""
    movements = stock_repo.find_all({}, limit=100)
    for m in movements:
        assert m["after_stock"] == m["before_stock"] + m["quantity"], (
            f"Invarian gagal pada record {m['_id']}: {m['after_stock']} != {m['before_stock']} + {m['quantity']}"
        )
        assert m["after_stock"] >= 0


# ----------------------------------------------------------------------
# 2. TEST TC-OR (Order & Status Transitions)
# ----------------------------------------------------------------------

def _create_helper_order(user_id, product, qty=2, pay_method=PaymentMethod.COD):
    from app.services.order_service import order_service
    from app.services.cart_service import cart_service
    from app.repositories import cart_repo

    cart_repo.clear(user_id)
    cart_service.add_to_cart(user_id, product["_id"], qty)
    order = order_service.create_order(
        user_id=user_id,
        contact_name="Budi Test",
        contact_phone="081234567890",
        fulfillment_method=FulfillmentMethod.PICKUP,
        payment_method=pay_method,
        idempotency_key=str(uuid.uuid4()),
    )
    return order


def test_tc_or_01_normal_flow_cod(admin_client, user_client, test_product):
    """TC-OR-01: Alur normal: pending -> confirmed -> processing -> ready_for_pickup -> completed (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1, pay_method=PaymentMethod.COD)
    oid = str(order["_id"])

    # 1. pending -> confirmed
    r1 = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})
    assert r1.status_code == 200

    # 2. confirmed -> processing (COD diizinkan walau unpaid)
    r2 = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "processing"})
    assert r2.status_code == 200

    # 3. processing -> ready_for_pickup
    r3 = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "ready_for_pickup"})
    assert r3.status_code == 200

    # Tandai COD lunas sebelum completed
    rp = admin_client.patch(f"/admin/orders/{oid}/payment", json={"action": "mark_cod_paid"})
    assert rp.status_code == 200

    # 4. ready_for_pickup -> completed
    r4 = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "completed"})
    assert r4.status_code == 200

    # Verifikasi status history
    final_order = order_repo.find_by_id(order["_id"])
    assert final_order["order_status"] == OrderStatus.COMPLETED
    assert final_order["payment_status"] == PaymentStatus.PAID
    statuses = [h["to"] for h in final_order["status_history"]]
    assert "confirmed" in statuses
    assert "processing" in statuses
    assert "ready_for_pickup" in statuses
    assert "completed" in statuses


def test_tc_or_02_invalid_transition(admin_client, user_client, test_product):
    """TC-OR-02: Transisi tidak valid: pending langsung ke completed -> 409 (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1)
    oid = str(order["_id"])

    resp = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "completed"})
    assert resp.status_code == 409


def test_tc_or_03_double_confirmation(admin_client, user_client, test_product):
    """TC-OR-03: Dua konfirmasi berurutan -> satu berhasil, kedua 409 (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1)
    oid = str(order["_id"])

    r1 = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})
    assert r1.status_code == 200

    r2 = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})
    assert r2.status_code == 409


def test_tc_or_04_transfer_unpaid_to_processing_rejected(admin_client, user_client, test_product):
    """TC-OR-04: Bank transfer belum lunas tidak dapat masuk ke processing -> 409 (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1, pay_method=PaymentMethod.BANK_TRANSFER)
    oid = str(order["_id"])

    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})
    # Belum lunas -> ke processing harus ditolak 409
    resp = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "processing"})
    assert resp.status_code == 409


def test_tc_or_05_completed_requires_paid(admin_client, user_client, test_product):
    """TC-OR-05: Selesai (completed) memerlukan pembayaran lunas (paid) (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1, pay_method=PaymentMethod.COD)
    oid = str(order["_id"])

    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})
    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "processing"})
    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "ready_for_pickup"})

    # Coba completed saat masih unpaid -> 409
    r_fail = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "completed"})
    assert r_fail.status_code == 409

    # Admin mark COD paid
    admin_client.patch(f"/admin/orders/{oid}/payment", json={"action": "mark_cod_paid"})

    # Sekarang completed harus berhasil
    r_ok = admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "completed"})
    assert r_ok.status_code == 200


def test_tc_or_06_07_08_payment_proof_lifecycle(admin_client, user_client, test_product):
    """TC-OR-06..08: Unggah bukti transfer valid, tolak file invalid, verifikasi & penolakan admin (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1, pay_method=PaymentMethod.BANK_TRANSFER)
    oid = str(order["_id"])

    # TC-OR-07: Unggah file invalid (.txt) -> 422
    fake_txt = io.BytesIO(b"ini bukan gambar")
    r_invalid = client_u.post(
        f"/orders/{oid}/payment-proof",
        data={"proof": (fake_txt, "fake.txt")},
        content_type="multipart/form-data",
    )
    assert r_invalid.status_code == 422

    # TC-OR-06: Unggah bukti valid JPG -> awaiting_verification
    img_stream, fname = create_sample_image_file()
    r_valid = client_u.post(
        f"/orders/{oid}/payment-proof",
        data={"proof": (img_stream, fname)},
        content_type="multipart/form-data",
    )
    assert r_valid.status_code == 302
    updated = order_repo.find_by_id(order["_id"])
    assert updated["payment_status"] == PaymentStatus.AWAITING_VERIFICATION

    # TC-OR-08: Admin menolak bukti (reject) -> failed
    r_reject = admin_client.patch(
        f"/admin/orders/{oid}/payment",
        json={"action": "reject", "note": "Nominal tidak sesuai mutasi rekening"},
    )
    assert r_reject.status_code == 200
    updated2 = order_repo.find_by_id(order["_id"])
    assert updated2["payment_status"] == PaymentStatus.FAILED

    # User unggah ulang bukti yang benar setelah ditolak
    img_stream2, fname2 = create_sample_image_file(format="PNG", filename="proof2.png")
    r_reupload = client_u.post(
        f"/orders/{oid}/payment-proof",
        data={"proof": (img_stream2, fname2)},
        content_type="multipart/form-data",
    )
    assert r_reupload.status_code == 302
    assert order_repo.find_by_id(order["_id"])["payment_status"] == PaymentStatus.AWAITING_VERIFICATION

    # Admin verifikasi bukti (verify) -> paid
    r_verify = admin_client.patch(f"/admin/orders/{oid}/payment", json={"action": "verify"})
    assert r_verify.status_code == 200
    assert order_repo.find_by_id(order["_id"])["payment_status"] == PaymentStatus.PAID


def test_tc_or_09_user_cancel_when_pending_restores_stock(user_client, test_product):
    """TC-OR-09: User membatalkan order saat pending -> cancelled, stok pulih penuh (P1)."""
    client_u, uid = user_client
    stock_before = product_repo.find_by_id(test_product["_id"])["stock"]
    order = _create_helper_order(uid, test_product, qty=3)
    oid = str(order["_id"])

    # Setelah order dibuat, stok berkurang 3
    assert product_repo.find_by_id(test_product["_id"])["stock"] == stock_before - 3

    # User batalkan
    resp = client_u.post(f"/orders/{oid}/cancel")
    assert resp.status_code == 302

    updated = order_repo.find_by_id(order["_id"])
    assert updated["order_status"] == OrderStatus.CANCELLED

    # Stok kembali utuh ke stock_before
    assert product_repo.find_by_id(test_product["_id"])["stock"] == stock_before

    # Periksa record restoration di stock_movements
    mv = stock_repo.collection.find_one({
        "reference_id": order["_id"],
        "movement_type": StockMovementType.RESTORATION,
    })
    assert mv is not None
    assert mv["quantity"] == 3


def test_tc_or_10_user_cancel_after_confirmed_rejected(admin_client, user_client, test_product):
    """TC-OR-10: User membatalkan setelah confirmed -> ditolak 409 (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1)
    oid = str(order["_id"])

    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})

    # Pelanggan coba batalkan
    resp = client_u.post(f"/orders/{oid}/cancel")
    assert resp.status_code == 409


def test_tc_or_11_admin_cancel_when_processing(admin_client, user_client, test_product):
    """TC-OR-11: Admin membatalkan saat processing -> stok pulih, record restoration (P1)."""
    client_u, uid = user_client
    stock_before = product_repo.find_by_id(test_product["_id"])["stock"]
    order = _create_helper_order(uid, test_product, qty=2)
    oid = str(order["_id"])

    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})
    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "processing"})

    # Admin batalkan
    resp = admin_client.patch(
        f"/admin/orders/{oid}/status",
        json={"status": "cancelled", "note": "Barang cacat pabrik"},
    )
    assert resp.status_code == 200

    updated = order_repo.find_by_id(order["_id"])
    assert updated["order_status"] == OrderStatus.CANCELLED
    assert product_repo.find_by_id(test_product["_id"])["stock"] == stock_before


def test_tc_or_12_double_cancel_safe(admin_client, user_client, test_product):
    """TC-OR-12: Pembatalan ganda -> kedua 409, stok hanya dipulihkan sekali (P1)."""
    client_u, uid = user_client
    stock_before = product_repo.find_by_id(test_product["_id"])["stock"]
    order = _create_helper_order(uid, test_product, qty=1)
    oid = str(order["_id"])

    r1 = client_u.post(f"/orders/{oid}/cancel")
    assert r1.status_code == 302

    r2 = client_u.post(f"/orders/{oid}/cancel")
    assert r2.status_code == 409

    # Stok tidak berlipat ganda
    assert product_repo.find_by_id(test_product["_id"])["stock"] == stock_before


def test_tc_or_13_cancel_paid_order_refunded(admin_client, user_client, test_product):
    """TC-OR-13: Pembatalan order lunas (paid) -> payment_status menjadi refunded (P2)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1)
    oid = str(order["_id"])

    # Tandai paid terlebih dahulu
    admin_client.patch(f"/admin/orders/{oid}/payment", json={"action": "mark_cod_paid"})
    assert order_repo.find_by_id(order["_id"])["payment_status"] == PaymentStatus.PAID

    # Batalkan oleh admin
    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "cancelled"})

    updated = order_repo.find_by_id(order["_id"])
    assert updated["order_status"] == OrderStatus.CANCELLED
    assert updated["payment_status"] == PaymentStatus.REFUNDED


def test_tc_or_14_cancel_order_with_voucher_restores_quota(user_client, test_product):
    """TC-OR-14: Voucher dikembalikan saat order dibatalkan -> used_count berkurang 1 (P3)."""
    client_u, uid = user_client
    from app.services.order_service import order_service
    from app.services.cart_service import cart_service
    from app.repositories import cart_repo

    vcode = f"VC-CANCEL-{uuid.uuid4().hex[:4].upper()}"
    promotion_repo.insert({
        "code": vcode,
        "discount_type": DiscountType.FIXED,
        "value": 5000,
        "min_order": 10000,
        "quota": 10,
        "used_count": 0,
        "starts_at": datetime.now(timezone.utc),
        "ends_at": datetime.now(timezone.utc).replace(year=2030),
        "is_active": True,
    })

    cart_repo.clear(uid)
    cart_service.add_to_cart(uid, test_product["_id"], 2)
    order = order_service.create_order(
        user_id=uid,
        contact_name="Voucher User",
        contact_phone="081234567890",
        fulfillment_method=FulfillmentMethod.PICKUP,
        payment_method=PaymentMethod.COD,
        idempotency_key=str(uuid.uuid4()),
        voucher_code=vcode,
    )
    oid = str(order["_id"])

    # Cek used_count naik jadi 1
    promo = promotion_repo.find_by_code(vcode)
    assert promo["used_count"] == 1

    # Batalkan order
    client_u.post(f"/orders/{oid}/cancel")

    # Cek used_count kembali ke 0
    promo_after = promotion_repo.find_by_code(vcode)
    assert promo_after["used_count"] == 0


def test_tc_or_15_completed_increments_sold_count(admin_client, user_client, test_product):
    """TC-OR-15: Order selesai menambah sold_count produk (P2)."""
    client_u, uid = user_client
    sold_before = test_product.get("sold_count", 0)
    order = _create_helper_order(uid, test_product, qty=4)
    oid = str(order["_id"])

    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "confirmed"})
    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "processing"})
    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "ready_for_pickup"})
    admin_client.patch(f"/admin/orders/{oid}/payment", json={"action": "mark_cod_paid"})
    admin_client.patch(f"/admin/orders/{oid}/status", json={"status": "completed"})

    prod_after = product_repo.find_by_id(test_product["_id"])
    assert prod_after["sold_count"] == sold_before + 4


def test_tc_sc_06_payment_proof_authorization(admin_client, user_client, other_user_client, test_product):
    """TC-SC-06: Akses berkas bukti transfer: user lain ditolak 404/403, pemilik & admin berhasil (P1)."""
    client_u, uid = user_client
    order = _create_helper_order(uid, test_product, qty=1, pay_method=PaymentMethod.BANK_TRANSFER)
    oid = str(order["_id"])

    # User unggah bukti transfer
    img_stream, fname = create_sample_image_file()
    client_u.post(
        f"/orders/{oid}/payment-proof",
        data={"proof": (img_stream, fname)},
        content_type="multipart/form-data",
    )

    # 1. User lain mencoba akses berkas bukti -> 404
    r_other = other_user_client.get(f"/orders/{oid}/payment-proof")
    assert r_other.status_code in [403, 404]

    # 2. Pemilik order mengakses berkas bukti -> 200
    r_owner = client_u.get(f"/orders/{oid}/payment-proof")
    assert r_owner.status_code == 200

    # 3. Admin mengakses berkas bukti -> 200
    r_admin = admin_client.get(f"/orders/{oid}/payment-proof")
    assert r_admin.status_code == 200
