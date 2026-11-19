"""Test integration untuk modul tambahan (Fase 8): Wishlist, Review, Promosi Admin, Notifikasi, Audit Log."""
import uuid
from datetime import datetime, timezone
import pytest
from bson import ObjectId

from app.repositories import (
    user_repo,
    product_repo,
    category_repo,
    order_repo,
    wishlist_repo,
    notification_repo,
    promotion_repo,
    review_repo,
)
from app.models.enums import UserRole, OrderStatus, PaymentStatus, DiscountType
from app.utils.security import hash_password


@pytest.fixture
def admin_client(app, db):
    c = app.test_client()
    email = "admin_add_feat@retailbrain.example"
    if not user_repo.find_by_email(email):
        user_repo.insert(
            name="Admin AddFeat",
            email=email,
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
        )
    c.post("/admin/login", data={"email": email, "password": "AdminPass123!"})
    return c


@pytest.fixture
def user_client(app, db):
    c = app.test_client()
    email = f"user_add_{uuid.uuid4().hex[:4]}@example.com"
    uid = user_repo.insert(
        name="User AddFeat",
        email=email,
        password_hash=hash_password("UserPass123!"),
        role=UserRole.USER,
        phone="081234567811",
    )
    c.post("/auth/login", data={"email": email, "password": "UserPass123!"})
    return c, uid


@pytest.fixture
def sample_product(db):
    cat = category_repo.find_by_slug("sembako")
    cid = cat["_id"] if cat else category_repo.insert(name="Sembako", slug="sembako")
    pid = product_repo.insert(
        sku=f"FEAT-{uuid.uuid4().hex[:4].upper()}",
        name="Produk Fitur Tambahan",
        category_id=cid,
        price=12000,
        stock=20,
    )
    return product_repo.find_by_id(pid)


def test_tc_wl_01_wishlist_lifecycle(user_client, sample_product):
    """TC-WL-01: Wishlist tanpa duplikat ($addToSet) dan hapus favorit (P3)."""
    c, uid = user_client
    pid_str = str(sample_product["_id"])

    # 1. Tambah pertama -> 201
    r1 = c.post("/wishlist/items", json={"product_id": pid_str})
    assert r1.status_code == 201

    # 2. Tambah kedua (produk sama) -> 201, tidak boleh ada duplikat dalam array
    r2 = c.post("/wishlist/items", json={"product_id": pid_str})
    assert r2.status_code == 201

    wdoc = wishlist_repo.find_by_user_id(uid)
    assert wdoc["product_ids"].count(sample_product["_id"]) == 1

    # 3. Tampilkan halaman wishlist
    r_view = c.get("/wishlist")
    assert r_view.status_code == 200
    assert sample_product["name"].encode() in r_view.data
    assert sample_product["sku"].encode() not in r_view.data

    # 4. Hapus dari wishlist
    r_del = c.delete(f"/wishlist/items/{pid_str}")
    assert r_del.status_code == 200
    wdoc_after = wishlist_repo.find_by_user_id(uid)
    assert sample_product["_id"] not in wdoc_after["product_ids"]


def test_tc_rv_01_02_03_reviews_lifecycle(user_client, sample_product):
    """TC-RV-01..03: Review setelah order completed, tolak order pending, tolak review ganda (P3)."""
    c, uid = user_client
    pid = sample_product["_id"]
    pid_str = str(pid)

    now = datetime.now(timezone.utc)
    # Order pending (belum completed)
    order_pending_id = ObjectId()
    order_repo.insert({
        "_id": order_pending_id,
        "order_number": f"RB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "user_id": uid,
        "items": [{"product_id": pid, "sku": sample_product["sku"], "name": sample_product["name"], "unit_price": 12000, "quantity": 1, "line_total": 12000}],
        "subtotal": 12000,
        "discount": 0,
        "delivery_fee": 0,
        "total": 12000,
        "fulfillment_method": "pickup",
        "payment_method": "cod",
        "payment_status": PaymentStatus.UNPAID,
        "order_status": OrderStatus.PENDING,
        "contact": {"name": "Reviewer", "phone": "0812345678"},
        "status_history": [{"from": None, "to": OrderStatus.PENDING, "actor_id": uid, "at": now, "note": "Pending"}],
        "idempotency_key": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
    })

    # TC-RV-02: Review saat order masih pending -> 403
    r_fail = c.post(
        f"/products/{pid_str}/reviews",
        json={"order_id": str(order_pending_id), "rating": 5, "comment": "Bagus banget"},
    )
    assert r_fail.status_code == 403

    # Buat order completed
    order_completed_id = ObjectId()
    order_repo.insert({
        "_id": order_completed_id,
        "order_number": f"RB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "user_id": uid,
        "items": [{"product_id": pid, "sku": sample_product["sku"], "name": sample_product["name"], "unit_price": 12000, "quantity": 1, "line_total": 12000}],
        "subtotal": 12000,
        "discount": 0,
        "delivery_fee": 0,
        "total": 12000,
        "fulfillment_method": "pickup",
        "payment_method": "cod",
        "payment_status": PaymentStatus.PAID,
        "order_status": OrderStatus.COMPLETED,
        "contact": {"name": "Reviewer", "phone": "0812345678"},
        "status_history": [{"from": None, "to": OrderStatus.COMPLETED, "actor_id": uid, "at": now, "note": "Completed"}],
        "idempotency_key": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
    })

    # TC-RV-01: Review valid pada order completed -> 201 & rating produk terbarui
    r_ok = c.post(
        f"/products/{pid_str}/reviews",
        json={"order_id": str(order_completed_id), "rating": 5, "comment": "Barang sangat memuaskan dan cepat sampai!"},
    )
    assert r_ok.status_code == 201

    prod_updated = product_repo.find_by_id(pid)
    assert prod_updated["rating_count"] >= 1
    assert prod_updated["rating_avg"] == 5.0

    # TC-RV-03: Review ganda untuk produk & order sama -> 409
    r_double = c.post(
        f"/products/{pid_str}/reviews",
        json={"order_id": str(order_completed_id), "rating": 4, "comment": "Review kedua"},
    )
    assert r_double.status_code == 409


def test_notifications_lifecycle(user_client):
    """Pengujian modul notifikasi in-app: baca per notif & baca semua."""
    c, uid = user_client

    # Buat notifikasi
    nid = notification_repo.insert(
        user_id=uid,
        title="Promo Spesial",
        message="Diskon 20% hari ini!",
        notif_type="system",
    )

    # Lihat notifikasi
    r_list = c.get("/notifications")
    assert r_list.status_code == 200
    assert b"Promo Spesial" in r_list.data

    # Tandai satu dibaca
    r_read = c.patch(f"/notifications/{nid}/read")
    assert r_read.status_code == 200

    # Tandai semua dibaca
    r_all = c.post("/notifications/read-all")
    assert r_all.status_code == 200
    assert notification_repo.count_unread(uid) == 0


def test_admin_promotions_and_audit_logs(admin_client):
    """Pengujian admin promosi dan audit logs."""
    # 1. Admin buat voucher
    code = f"DISC{uuid.uuid4().hex[:4].upper()}"
    r_create = admin_client.post(
        "/admin/promotions",
        json={
            "code": code,
            "discount_type": "fixed",
            "value": 5000,
            "min_order": 20000,
            "quota": 50,
        },
    )
    assert r_create.status_code == 201

    # Coba buat lagi dengan kode sama -> 409
    r_dup = admin_client.post(
        "/admin/promotions",
        json={"code": code, "discount_type": "fixed", "value": 5000},
    )
    assert r_dup.status_code == 409

    # 2. Admin melihat halaman promosi
    r_list = admin_client.get("/admin/promotions")
    assert r_list.status_code == 200
    assert code.encode() in r_list.data

    # 3. Admin melihat audit logs
    r_audit = admin_client.get("/admin/audit-logs")
    assert r_audit.status_code == 200
    assert b"Log Audit Sistem" in r_audit.data


def test_admin_users_and_reviews_management(admin_client, user_client, sample_product):
    """Pengujian admin user management & review moderation (Bab 14.6)."""
    c_user, uid = user_client
    admin_user = user_repo.find_by_email("admin_add_feat@retailbrain.example")
    admin_id_str = str(admin_user["_id"])
    uid_str = str(uid)

    # 1. Admin melihat daftar user
    r_users = admin_client.get("/admin/users")
    assert r_users.status_code == 200
    assert b"Manajemen Pengguna" in r_users.data
    assert b"Admin AddFeat" in r_users.data

    # Filter pencarian user
    r_search = admin_client.get("/admin/users?q=Admin")
    assert r_search.status_code == 200
    assert b"Admin AddFeat" in r_search.data

    # 2. Admin mencoba menonaktifkan akun sendiri -> 403 Forbidden
    r_self = admin_client.patch(f"/admin/users/{admin_id_str}", json={"is_active": False})
    assert r_self.status_code == 403

    # 3. Admin menonaktifkan akun user lain -> 200 OK
    r_deact = admin_client.patch(f"/admin/users/{uid_str}", json={"is_active": False})
    assert r_deact.status_code == 200
    u_doc = user_repo.find_by_id(uid)
    assert u_doc["is_active"] is False

    # 4. Admin mengaktifkan kembali akun user -> 200 OK
    r_act = admin_client.patch(f"/admin/users/{uid_str}", json={"is_active": True})
    assert r_act.status_code == 200
    u_doc2 = user_repo.find_by_id(uid)
    assert u_doc2["is_active"] is True

    # 5. Review moderation
    # Buat review untuk sample_product
    pid = sample_product["_id"]
    rev_id = review_repo.insert(
        user_id=uid,
        product_id=pid,
        order_id=ObjectId(),
        rating=5,
        comment="Produk mantap admin test!",
        is_visible=True,
    )
    product_repo.update_rating(pid, 5.0, 1)

    # Admin lihat daftar review
    r_rev_list = admin_client.get("/admin/reviews")
    assert r_rev_list.status_code == 200
    assert b"Moderasi Review" in r_rev_list.data
    assert b"Produk mantap admin test!" in r_rev_list.data

    # Cek ulasan tampil di halaman publik detail produk (hanya is_visible=True)
    r_detail = c_user.get(f"/products/{pid}")
    assert r_detail.status_code == 200
    assert b"Produk mantap admin test!" in r_detail.data

    # Admin sembunyikan review (toggle is_visible -> False)
    r_hide = admin_client.patch(f"/admin/reviews/{rev_id}", json={"is_visible": False})
    assert r_hide.status_code == 200
    rev_doc = review_repo.find_by_id(rev_id)
    assert rev_doc["is_visible"] is False

    # Rating produk terupdate setelah disembunyikan (karena tidak ada review visible lagi -> rating 0.0)
    p_doc = product_repo.find_by_id(pid)
    assert p_doc["rating_count"] == 0
    assert p_doc["rating_avg"] == 0.0

    # Cek ulasan TIDAK tampil di halaman publik detail produk saat tersembunyi
    r_detail_hidden = c_user.get(f"/products/{pid}")
    assert r_detail_hidden.status_code == 200
    assert b"Produk mantap admin test!" not in r_detail_hidden.data

    # Admin tampilkan kembali review
    r_show = admin_client.patch(f"/admin/reviews/{rev_id}", json={"is_visible": True})
    assert r_show.status_code == 200
    rev_doc2 = review_repo.find_by_id(rev_id)
    assert rev_doc2["is_visible"] is True
    p_doc2 = product_repo.find_by_id(pid)
    assert p_doc2["rating_count"] == 1
    assert p_doc2["rating_avg"] == 5.0

    # Cek ulasan tampil kembali di halaman publik detail produk
    r_detail_shown = c_user.get(f"/products/{pid}")
    assert r_detail_shown.status_code == 200
    assert b"Produk mantap admin test!" in r_detail_shown.data


