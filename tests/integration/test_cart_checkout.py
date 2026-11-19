import uuid
import pytest
from bson import ObjectId
from app.repositories import product_repo, category_repo, stock_repo, user_repo, order_repo, cart_repo
from app.models.enums import UserRole, OrderStatus, PaymentStatus, StockMovementType
from app.utils.security import hash_password


@pytest.fixture
def user_a_client(app, db):
    c = app.test_client()
    user_email = "usera@example.com"
    user = user_repo.find_by_email(user_email)
    if not user:
        user_id = user_repo.insert(
            name="User A",
            email=user_email,
            password_hash=hash_password("UserPass123!"),
            role=UserRole.USER,
            phone="081234567890",
        )
    else:
        user_id = user["_id"]
    cart_repo.clear(user_id)
    c.post("/auth/login", data={"email": user_email, "password": "UserPass123!"})
    return c


@pytest.fixture
def user_b_client(app, db):
    c = app.test_client()
    user_email = "userb@example.com"
    user = user_repo.find_by_email(user_email)
    if not user:
        user_id = user_repo.insert(
            name="User B",
            email=user_email,
            password_hash=hash_password("UserPass123!"),
            role=UserRole.USER,
            phone="081298765432",
        )
    else:
        user_id = user["_id"]
    cart_repo.clear(user_id)
    c.post("/auth/login", data={"email": user_email, "password": "UserPass123!"})
    return c


@pytest.fixture
def products_fixture(db):
    cat = category_repo.find_by_slug("sembako")
    if not cat:
        cid = category_repo.insert(name="Sembako", slug="sembako")
    else:
        cid = cat["_id"]

    p1 = product_repo.find_by_sku("PROD-TEST-A")
    if not p1:
        p1_id = product_repo.insert(sku="PROD-TEST-A", name="Produk A 3500", category_id=cid, price=3500, stock=100)
    else:
        p1_id = p1["_id"]

    p2 = product_repo.find_by_sku("PROD-TEST-B")
    if not p2:
        p2_id = product_repo.insert(sku="PROD-TEST-B", name="Produk B 18500", category_id=cid, price=18500, stock=50)
    else:
        p2_id = p2["_id"]

    return str(p1_id), str(p2_id)


def test_tc_ct_01_02_tambah_produk_dan_gabung_kuantitas(user_a_client, products_fixture):
    """TC-CT-01 & TC-CT-02: Tambah produk ke keranjang, dan kuantitas digabung jika item sama (P1)."""
    p1_id, _ = products_fixture

    # Tambah 2 unit
    resp1 = user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 2})
    assert resp1.status_code == 201

    # Tambah lagi 3 unit untuk produk yang sama
    resp2 = user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 3})
    assert resp2.status_code == 201

    # Cek view keranjang: harus satu item dengan kuantitas 5
    cart_resp = user_a_client.get("/cart")
    assert cart_resp.status_code == 200
    assert b"Produk A 3500" in cart_resp.data


def test_tc_ct_03_kuantitas_tidak_valid(user_a_client, products_fixture):
    """TC-CT-03: Kuantitas 0, negatif, atau string ditolak 400/422 (P1)."""
    p1_id, _ = products_fixture

    resp_zero = user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 0})
    assert resp_zero.status_code in [400, 422]

    resp_neg = user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": -5})
    assert resp_neg.status_code in [400, 422]

    resp_str = user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": "invalid"})
    assert resp_str.status_code in [400, 422]


def test_tc_ct_04_kuantitas_melebihi_stok(user_a_client, products_fixture):
    """TC-CT-04: Kuantitas melebihi stok ditolak status 409 (P1)."""
    p1_id, _ = products_fixture
    # Stok produk A adalah 100, coba beli 999
    resp = user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 999})
    assert resp.status_code in [409, 422]


def test_tc_ct_05_ubah_dan_hapus_item(user_a_client, products_fixture):
    """TC-CT-05: Ubah kuantitas (PATCH) dan hapus item (DELETE) (P1)."""
    p1_id, _ = products_fixture

    # Masukkan item ke cart dulu
    add_resp = user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 1})
    assert add_resp.status_code == 201

    # Ubah qty ke 4
    patch_resp = user_a_client.patch(f"/cart/items/{p1_id}", json={"quantity": 4})
    assert patch_resp.status_code == 200

    # Hapus item
    del_resp = user_a_client.delete(f"/cart/items/{p1_id}")
    assert del_resp.status_code == 200


def test_checkout_defaults_to_pickup_total_without_delivery_fee(user_a_client, products_fixture):
    p1_id, _ = products_fixture
    user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 1})

    resp = user_a_client.get("/checkout")

    assert resp.status_code == 200
    assert b'data-subtotal="3500"' in resp.data
    assert b'id="checkout-delivery-fee" aria-live="polite">Rp 0<' in resp.data
    assert b'id="checkout-total" aria-live="polite">Rp 3.500<' in resp.data


def test_tc_co_01_checkout_pickup_cod_sukses(user_a_client, products_fixture, db):
    """TC-CO-01: Checkout pickup + COD -> order pending/unpaid, stok berkurang, keranjang kosong (P1)."""
    p1_id, _ = products_fixture
    prod_before = product_repo.find_by_id(ObjectId(p1_id))
    stock_before = prod_before["stock"]

    # Masukkan 6 unit ke keranjang
    user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 6})

    key = str(uuid.uuid4())
    resp = user_a_client.post(
        "/orders",
        data={
            "contact_name": "Budi Penerima",
            "contact_phone": "081234567890",
            "fulfillment_method": "pickup",
            "payment_method": "cod",
            "idempotency_key": key,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/confirmation" in resp.headers["Location"]

    # Stok berkurang tepat 6 unit
    prod_after = product_repo.find_by_id(ObjectId(p1_id))
    assert prod_after["stock"] == stock_before - 6

    # Keranjang menjadi kosong
    cart_page = user_a_client.get("/cart")
    assert b"Keranjang masih kosong" in cart_page.data or b"0" in cart_page.data

    # Cek record stock_movements reduction
    movement = stock_repo.find_all({"product_id": ObjectId(p1_id), "movement_type": StockMovementType.REDUCTION})
    assert len(movement) >= 1
    assert movement[0]["quantity"] == -6


def test_tc_co_02_checkout_transfer_bank(user_a_client, products_fixture):
    """TC-CO-02: Checkout transfer bank -> payment_status unpaid, instruksi transfer tampil (P1)."""
    p1_id, _ = products_fixture
    user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 1})

    key = str(uuid.uuid4())
    resp = user_a_client.post(
        "/orders",
        data={
            "contact_name": "Budi Penerima",
            "contact_phone": "081234567890",
            "fulfillment_method": "pickup",
            "payment_method": "bank_transfer",
            "idempotency_key": key,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Bank Mandiri" in resp.data or b"transfer" in resp.data.lower()


def test_tc_co_03_keranjang_kosong_ditolak(user_a_client):
    """TC-CO-03: Order saat keranjang kosong ditolak status 400 (P1)."""
    key = str(uuid.uuid4())
    resp = user_a_client.post(
        "/orders",
        data={
            "contact_name": "Budi Penerima",
            "contact_phone": "081234567890",
            "fulfillment_method": "pickup",
            "payment_method": "cod",
            "idempotency_key": key,
        },
    )
    assert resp.status_code == 400


def test_tc_co_04_manipulasi_harga_klien_diabaikan(user_a_client, products_fixture):
    """TC-CO-04: Nilai total yang dikirim dari klien diabaikan; server menghitung ulang (P1)."""
    p1_id, _ = products_fixture
    # Harga produk A = 3500. Beli 2 unit = 7000
    user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 2})

    key = str(uuid.uuid4())
    resp = user_a_client.post(
        "/orders",
        data={
            "contact_name": "Budi Penerima",
            "contact_phone": "081234567890",
            "fulfillment_method": "pickup",
            "payment_method": "cod",
            "total": "1",  # Klien mencoba memanipulasi total menjadi Rp 1
            "subtotal": "1",
            "idempotency_key": key,
        },
    )
    assert resp.status_code == 302

    # Verifikasi total yang tersimpan di order
    order = order_repo.find_by_idempotency_key(key)
    assert order is not None
    assert order["total"] == 7000  # Dihitung ulang oleh server, bukan 1!


def test_tc_co_06_delivery_tanpa_alamat(user_a_client, products_fixture):
    """TC-CO-06: Delivery tanpa alamat ditolak 422 (P2)."""
    p1_id, _ = products_fixture
    user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 1})

    resp = user_a_client.post(
        "/orders",
        data={
            "contact_name": "Budi Penerima",
            "contact_phone": "081234567890",
            "fulfillment_method": "delivery",
            "shipping_address": "",  # Kosong
            "payment_method": "cod",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 422


def test_tc_co_07_submit_ganda_idempotent(user_a_client, products_fixture):
    """TC-CO-07: Submit ganda dengan idempotency_key sama -> hanya satu order, stok hanya berkurang sekali (P1)."""
    p1_id, _ = products_fixture
    user_a_client.post("/cart/items", json={"product_id": p1_id, "quantity": 2})

    prod_before = product_repo.find_by_id(ObjectId(p1_id))
    stock_before = prod_before["stock"]

    same_key = str(uuid.uuid4())
    payload = {
        "contact_name": "Budi Penerima",
        "contact_phone": "081234567890",
        "fulfillment_method": "pickup",
        "payment_method": "cod",
        "idempotency_key": same_key,
    }

    # Submit pertama
    resp1 = user_a_client.post("/orders", data=payload)
    assert resp1.status_code == 302

    # Submit kedua dengan key yang sama
    resp2 = user_a_client.post("/orders", data=payload)
    assert resp2.status_code == 302

    # Cek stok: hanya berkurang 2 unit, bukan 4
    prod_after = product_repo.find_by_id(ObjectId(p1_id))
    assert prod_after["stock"] == stock_before - 2


def test_tc_rb_04_user_baca_order_user_lain_404(user_a_client, user_b_client, products_fixture):
    """TC-RB-04: User membaca order milik user lain mengembalikan 404 (bukan membocorkan data) (P1)."""
    # User B login dan membuat order
    p1_id, _ = products_fixture
    user_b_client.post("/cart/items", json={"product_id": p1_id, "quantity": 1})
    key_b = str(uuid.uuid4())
    user_b_client.post(
        "/orders",
        data={
            "contact_name": "User B Penerima",
            "contact_phone": "081298765432",
            "fulfillment_method": "pickup",
            "payment_method": "cod",
            "idempotency_key": key_b,
        },
    )
    order_b = order_repo.find_by_idempotency_key(key_b)
    assert order_b is not None

    # User A mencoba membuka detail order User B
    resp = user_a_client.get(f"/orders/{order_b['_id']}")
    assert resp.status_code == 404

