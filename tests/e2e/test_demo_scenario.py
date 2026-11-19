"""Skenario Demo End-to-End sesuai Bab 23.2 Blueprint RetailBrain.
Memverifikasi 9 langkah demonstrasi lengkap dari login admin hingga pembatalan & otorisasi.
"""
import io
import uuid
import pytest
from bson import ObjectId
from PIL import Image

from app.repositories import user_repo, product_repo, category_repo, order_repo, stock_repo
from app.models.enums import UserRole, OrderStatus, PaymentStatus, StockMovementType


def create_sample_receipt():
    stream = io.BytesIO()
    img = Image.new("RGB", (300, 300), color=(240, 240, 240))
    img.save(stream, format="JPEG")
    stream.seek(0)
    return stream, "struk_transfer_bca.jpg"


def test_complete_demo_scenario_bab_23_2(app, db):
    """Skenario Demo End-to-End Bab 23.2:
    1. Admin login, membuat kategori dan dua produk dengan stok awal.
    2. User mendaftar, login, mencari produk, menambah ke keranjang.
    3. Checkout (pickup + transfer manual), konfirmasi order tampil, stok berkurang.
    4. User mengunggah bukti transfer.
    5. Admin memverifikasi pembayaran, memproses order sampai selesai.
    6. User melihat status berubah dan riwayat order.
    7. Admin membuka laporan penjualan (menampilkan order tadi) dan riwayat stok.
    8. Demonstrasi pembatalan order dan pemulihan stok.
    9. Demonstrasi pembatasan akses: user membuka /admin/dashboard (403).
    """
    # -------------------------------------------------------------
    # LANGKAH 1: Admin login, membuat kategori dan dua produk dengan stok awal
    # -------------------------------------------------------------
    admin_client = app.test_client()
    from app.utils.security import hash_password

    admin_email = "admin_demo@retailbrain.example"
    admin = user_repo.find_by_email(admin_email)
    if not admin:
        user_repo.insert(
            name="Admin Demonstrasi",
            email=admin_email,
            password_hash=hash_password("AdminDemo123!"),
            role=UserRole.ADMIN,
        )

    login_admin_res = admin_client.post(
        "/admin/login",
        data={"email": admin_email, "password": "AdminDemo123!"},
        follow_redirects=True,
    )
    assert login_admin_res.status_code == 200

    # Buat Kategori Minuman
    cat_slug = f"minuman-{uuid.uuid4().hex[:4]}"
    cat_res = admin_client.post(
        "/admin/categories",
        data={"name": "Minuman Segar", "slug": cat_slug, "description": "Aneka minuman dalam kemasan"},
        follow_redirects=True,
    )
    assert cat_res.status_code == 200
    category = category_repo.find_by_slug(cat_slug)
    assert category is not None

    # Buat Produk 1: Air Mineral 600ml (Stok awal 50)
    sku_p1 = f"MNM-{uuid.uuid4().hex[:4].upper()}"
    p1_res = admin_client.post(
        "/admin/products",
        data={
            "sku": sku_p1,
            "name": "Air Mineral 600ml",
            "category_id": str(category["_id"]),
            "price": "4000",
            "stock": "50",
            "min_stock": "10",
            "description": "Air mineral pegunungan alami",
        },
        follow_redirects=True,
    )
    assert p1_res.status_code == 200
    p1 = product_repo.find_by_sku(sku_p1)
    assert p1 is not None and p1["stock"] == 50

    # Buat Produk 2: Teh Botol 450ml (Stok awal 30)
    sku_p2 = f"MNM-{uuid.uuid4().hex[:4].upper()}"
    p2_res = admin_client.post(
        "/admin/products",
        data={
            "sku": sku_p2,
            "name": "Teh Botol Melati 450ml",
            "category_id": str(category["_id"]),
            "price": "6000",
            "stock": "30",
            "min_stock": "8",
            "description": "Teh rasa melati asli",
        },
        follow_redirects=True,
    )
    assert p2_res.status_code == 200
    p2 = product_repo.find_by_sku(sku_p2)
    assert p2 is not None and p2["stock"] == 30

    # Verifikasi stock movements tipe initial terbentuk
    mv_initial_1 = stock_repo.collection.find_one({"product_id": p1["_id"], "movement_type": "initial"})
    assert mv_initial_1 is not None
    assert mv_initial_1["quantity"] == 50

    # -------------------------------------------------------------
    # LANGKAH 2: User mendaftar, login, mencari produk, menambah ke keranjang
    # -------------------------------------------------------------
    user_client = app.test_client()
    user_email = f"budi_demo_{uuid.uuid4().hex[:4]}@example.com"
    user_pass = "BudiDemo123!"

    reg_res = user_client.post(
        "/auth/register",
        data={
            "name": "Budi Santoso",
            "email": user_email,
            "password": user_pass,
            "confirm_password": user_pass,
            "phone": "081234567890",
        },
        follow_redirects=True,
    )
    assert reg_res.status_code == 200

    login_user_res = user_client.post(
        "/auth/login",
        data={"email": user_email, "password": user_pass},
        follow_redirects=True,
    )
    assert login_user_res.status_code == 200

    # Cari produk
    search_res = user_client.get(f"/products?q=Air+Mineral")
    assert search_res.status_code == 200
    assert b"Air Mineral 600ml" in search_res.data
    assert sku_p1.encode() not in search_res.data

    # Tambah 2 unit Air Mineral dan 1 unit Teh Botol ke keranjang belanja
    add_p1 = user_client.post("/cart/items", json={"product_id": str(p1["_id"]), "quantity": 2})
    assert add_p1.status_code == 201

    add_p2 = user_client.post("/cart/items", json={"product_id": str(p2["_id"]), "quantity": 1})
    assert add_p2.status_code == 201

    # -------------------------------------------------------------
    # LANGKAH 3: Checkout (pickup + transfer manual), konfirmasi order tampil, stok berkurang
    # -------------------------------------------------------------
    # Ambil halaman checkout untuk mendapatkan form data
    co_page = user_client.get("/checkout")
    assert co_page.status_code == 200

    idempotency_key = str(uuid.uuid4())
    create_order_res = user_client.post(
        "/orders",
        data={
            "contact_name": "Budi Santoso",
            "contact_phone": "081234567890",
            "fulfillment_method": "pickup",
            "payment_method": "bank_transfer",
            "idempotency_key": idempotency_key,
        },
        follow_redirects=True,
    )
    assert create_order_res.status_code == 200

    # Cari order yang baru saja terbentuk
    order_1 = order_repo.find_by_idempotency_key(idempotency_key)
    assert order_1 is not None
    oid_1 = str(order_1["_id"])

    # Total order = (2 * 4000) + (1 * 6000) = 14000
    assert order_1["subtotal"] == 14000
    assert order_1["total"] == 14000
    assert order_1["order_status"] == OrderStatus.PENDING
    assert order_1["payment_status"] == PaymentStatus.UNPAID

    # Verifikasi stok berkurang secara atomik
    p1_after = product_repo.find_by_id(p1["_id"])
    p2_after = product_repo.find_by_id(p2["_id"])
    assert p1_after["stock"] == 50 - 2  # 48
    assert p2_after["stock"] == 30 - 1  # 29

    # -------------------------------------------------------------
    # LANGKAH 4: User mengunggah bukti transfer
    # -------------------------------------------------------------
    receipt_stream, receipt_fname = create_sample_receipt()
    upload_res = user_client.post(
        f"/orders/{oid_1}/payment-proof",
        data={"proof": (receipt_stream, receipt_fname)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload_res.status_code == 200

    order_1_uploaded = order_repo.find_by_id(order_1["_id"])
    assert order_1_uploaded["payment_status"] == PaymentStatus.AWAITING_VERIFICATION
    assert order_1_uploaded["payment_proof"] is not None

    # -------------------------------------------------------------
    # LANGKAH 5: Admin memverifikasi pembayaran, memproses order sampai selesai
    # -------------------------------------------------------------
    # Admin melihat antrean verifikasi
    payments_queue = admin_client.get("/admin/payments")
    assert payments_queue.status_code == 200
    assert order_1["order_number"].encode() in payments_queue.data

    # Admin verifikasi pembayaran -> status jadi paid
    verify_res = admin_client.patch(
        f"/admin/orders/{oid_1}/payment",
        json={"action": "verify"},
    )
    assert verify_res.status_code == 200
    assert order_repo.find_by_id(order_1["_id"])["payment_status"] == PaymentStatus.PAID

    # Transisi alur: confirmed -> processing -> ready_for_pickup -> completed
    r_conf = admin_client.patch(f"/admin/orders/{oid_1}/status", json={"status": "confirmed"})
    assert r_conf.status_code == 200

    r_proc = admin_client.patch(f"/admin/orders/{oid_1}/status", json={"status": "processing"})
    assert r_proc.status_code == 200

    r_ready = admin_client.patch(f"/admin/orders/{oid_1}/status", json={"status": "ready_for_pickup"})
    assert r_ready.status_code == 200

    r_comp = admin_client.patch(f"/admin/orders/{oid_1}/status", json={"status": "completed"})
    assert r_comp.status_code == 200

    # sold_count produk bertambah
    assert product_repo.find_by_id(p1["_id"])["sold_count"] == 2
    assert product_repo.find_by_id(p2["_id"])["sold_count"] == 1

    # -------------------------------------------------------------
    # LANGKAH 6: User melihat status berubah dan riwayat order
    # -------------------------------------------------------------
    user_orders_page = user_client.get("/orders/my")
    assert user_orders_page.status_code == 200
    assert order_1["order_number"].encode() in user_orders_page.data

    user_order_detail = user_client.get(f"/orders/{oid_1}")
    assert user_order_detail.status_code == 200
    assert b"completed" in user_order_detail.data.lower()
    assert b"paid" in user_order_detail.data.lower()

    # -------------------------------------------------------------
    # LANGKAH 7: Admin membuka laporan penjualan dan riwayat stok
    # -------------------------------------------------------------
    sales_rep = admin_client.get("/admin/reports/sales", headers={"Accept": "application/json"})
    assert sales_rep.status_code == 200
    sales_data = sales_rep.get_json()["data"]
    assert sales_data["grand_total_sales"] >= 14000
    assert sales_data["grand_total_orders"] >= 1

    movements_rep = admin_client.get("/admin/inventory/movements")
    assert movements_rep.status_code == 200
    assert sku_p1.encode() in movements_rep.data
    assert sku_p2.encode() in movements_rep.data

    # -------------------------------------------------------------
    # LANGKAH 8: Demonstrasi pembatalan order dan pemulihan stok
    # -------------------------------------------------------------
    # User buat order kedua untuk 5 unit Teh Botol
    user_client.post("/cart/items", json={"product_id": str(p2["_id"]), "quantity": 5})
    key_cancel = str(uuid.uuid4())
    user_client.post(
        "/orders",
        data={
            "contact_name": "Budi Santoso",
            "contact_phone": "081234567890",
            "fulfillment_method": "pickup",
            "payment_method": "cod",
            "idempotency_key": key_cancel,
        },
    )
    order_2 = order_repo.find_by_idempotency_key(key_cancel)
    assert order_2 is not None
    oid_2 = str(order_2["_id"])

    # Stok Teh Botol berkurang 5 (dari 29 menjadi 24)
    assert product_repo.find_by_id(p2["_id"])["stock"] == 24

    # User batalkan order saat status masih pending
    cancel_res = user_client.post(f"/orders/{oid_2}/cancel", follow_redirects=True)
    assert cancel_res.status_code == 200

    order_2_after = order_repo.find_by_id(order_2["_id"])
    assert order_2_after["order_status"] == OrderStatus.CANCELLED

    # Stok Teh Botol pulih penuh kembali ke 29!
    assert product_repo.find_by_id(p2["_id"])["stock"] == 29

    # Record restoration tercatat
    mv_restore = stock_repo.collection.find_one({
        "reference_id": order_2["_id"],
        "movement_type": StockMovementType.RESTORATION,
    })
    assert mv_restore is not None
    assert mv_restore["quantity"] == 5

    # -------------------------------------------------------------
    # LANGKAH 9: Demonstrasi pembatasan akses (RBAC & Isolation)
    # -------------------------------------------------------------
    # 9a. User biasa membuka /admin/dashboard -> 403 Forbidden
    r_user_admin = user_client.get("/admin/dashboard")
    assert r_user_admin.status_code == 403

    # 9b. Admin mencoba mengakses /cart (rute pelanggan) -> 403 Forbidden (Keputusan D8)
    r_admin_cart = admin_client.get("/cart")
    assert r_admin_cart.status_code == 403

    # 9c. User lain mencoba membaca order Budi -> 404 Not Found
    other_client = app.test_client()
    other_email = f"other_{uuid.uuid4().hex[:4]}@example.com"
    other_client.post(
        "/auth/register",
        data={
            "name": "Other User",
            "email": other_email,
            "password": "OtherPass123!",
            "confirm_password": "OtherPass123!",
            "phone": "081299998888",
        },
    )
    other_client.post("/auth/login", data={"email": other_email, "password": "OtherPass123!"})
    r_idor = other_client.get(f"/orders/{oid_1}")
    assert r_idor.status_code == 404

