import io
import pytest
from bson import ObjectId
from app.repositories import product_repo, category_repo, stock_repo, user_repo
from app.models.enums import UserRole, StockMovementType
from app.utils.security import hash_password
from PIL import Image


@pytest.fixture
def admin_client(client, db):
    # Buat akun admin untuk testing
    admin_email = "admin_catalog@retailbrain.example"
    admin = user_repo.find_by_email(admin_email)
    if not admin:
        admin_id = user_repo.insert(
            name="Admin Catalog",
            email=admin_email,
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
        )
    client.post("/admin/login", data={"email": admin_email, "password": "AdminPass123!"})
    return client


@pytest.fixture
def sample_category(db):
    cat = category_repo.find_by_slug("sembako")
    if not cat:
        cid = category_repo.insert(name="Sembako", slug="sembako", description="Bahan pokok")
        return category_repo.find_by_id(cid)
    return cat


def test_tc_pr_01_create_product_valid(admin_client, sample_category):
    """TC-PR-01: Buat produk valid -> produk dibuat, stock_movements initial terbentuk (P1)."""
    resp = admin_client.post(
        "/admin/products",
        data={
            "sku": "SMB-0001",
            "name": "Beras Premium 5 kg",
            "category_id": str(sample_category["_id"]),
            "price": "65000",
            "stock": "50",
            "min_stock": "10",
            "description": "Beras pulen berkualitas.",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    prod = product_repo.find_by_sku("SMB-0001")
    assert prod is not None
    assert prod["price"] == 65000
    assert prod["stock"] == 50
    assert prod["is_active"] is True

    # Periksa record stock_movements initial
    movements = stock_repo.find_all({"product_id": prod["_id"]})
    assert len(movements) == 1
    assert movements[0]["movement_type"] == StockMovementType.INITIAL
    assert movements[0]["quantity"] == 50
    assert movements[0]["before_stock"] == 0
    assert movements[0]["after_stock"] == 50


def test_tc_pr_02_sku_ganda_ditolak(admin_client, sample_category):
    """TC-PR-02: SKU yang sudah ada ditolak dengan status 409 (P1)."""
    resp = admin_client.post(
        "/admin/products",
        data={
            "sku": "SMB-0001",  # Sudah dibuat di test sebelumnya
            "name": "Beras Lain",
            "category_id": str(sample_category["_id"]),
            "price": "70000",
            "stock": "10",
        },
    )
    assert resp.status_code == 409


def test_tc_pr_03_harga_stok_tidak_valid(admin_client, sample_category):
    """TC-PR-03: Harga negatif atau stok non-integer ditolak dengan status 422 (P1)."""
    resp_negative_price = admin_client.post(
        "/admin/products",
        data={
            "sku": "SMB-0002",
            "name": "Produk Murah",
            "category_id": str(sample_category["_id"]),
            "price": "-1000",
            "stock": "10",
        },
    )
    assert resp_negative_price.status_code == 422

    resp_invalid_stock = admin_client.post(
        "/admin/products",
        data={
            "sku": "SMB-0003",
            "name": "Produk Gagal",
            "category_id": str(sample_category["_id"]),
            "price": "10000",
            "stock": "abc",
        },
    )
    assert resp_invalid_stock.status_code == 422


def test_tc_pr_04_kategori_tidak_ada(admin_client):
    """TC-PR-04: category_id acak ditolak 422 (P2)."""
    resp = admin_client.post(
        "/admin/products",
        data={
            "sku": "SMB-0004",
            "name": "Produk Kategori Palsu",
            "category_id": str(ObjectId()),
            "price": "10000",
            "stock": "5",
        },
    )
    assert resp.status_code == 422


def test_tc_pr_05_soft_delete_produk(admin_client, client):
    """TC-PR-05: Nonaktifkan produk -> is_active=false, hilang dari katalog, detail 404 (P1)."""
    prod = product_repo.find_by_sku("SMB-0001")
    assert prod is not None

    del_resp = admin_client.delete(f"/admin/products/{prod['_id']}")
    assert del_resp.status_code == 200

    # Cek di database: is_active menjadi False
    updated_prod = product_repo.find_by_id(prod["_id"])
    assert updated_prod["is_active"] is False

    # Cek detail publik: harus 404
    detail_resp = client.get(f"/products/{prod['_id']}")
    assert detail_resp.status_code == 404


def test_tc_pr_06_ubah_stok_lewat_patch_produk_ditolak(admin_client, sample_category):
    """TC-PR-06: Ubah stok lewat PATCH /admin/products/<id> ditolak 422 (P1)."""
    pid = product_repo.insert(
        sku="SMB-TEST-PATCH",
        name="Produk Patch",
        category_id=sample_category["_id"],
        price=5000,
        stock=10,
    )
    resp = admin_client.patch(f"/admin/products/{pid}", json={"stock": 999})
    assert resp.status_code == 422
    assert "inventori" in resp.get_json()["error"]["message"]


def test_tc_pr_07_08_09_pencarian_nama_sku_regex(client, sample_category):
    """TC-PR-07, 08, 09: Pencarian berdasarkan nama, SKU, dan karakter regex aman (P1)."""
    product_repo.insert(
        sku="MNM-TEST-MINERAL",
        name="Air Mineral Alami Pegunungan",
        category_id=sample_category["_id"],
        price=4000,
        stock=100,
        is_active=True,
    )

    # TC-PR-07: Cari nama parsial
    resp_name = client.get("/products?q=mineral")
    assert resp_name.status_code == 200
    assert b"Air Mineral Alami Pegunungan" in resp_name.data

    # TC-PR-08: Cari SKU persis
    resp_sku = client.get("/products?q=MNM-TEST-MINERAL")
    assert resp_sku.status_code == 200
    assert b"Air Mineral Alami Pegunungan" in resp_sku.data

    # TC-PR-09: Regex character q=.* tidak boleh match semua karena di-escape
    resp_regex = client.get("/products?q=.*")
    assert resp_regex.status_code == 200


def test_tc_pr_10_filter_kategori_harga_sort(client, sample_category):
    """TC-PR-10: Filter kategori, rentang harga, dan sorting (P1)."""
    resp = client.get(f"/products?category={sample_category['slug']}&min_price=1000&max_price=50000&sort=price_asc")
    assert resp.status_code == 200


def test_tc_va_01_object_id_tidak_valid(client):
    """TC-VA-01: ObjectId tidak valid di URL mengembalikan 404 (bukan 500) (P1)."""
    resp = client.get("/products/abc")
    assert resp.status_code == 404


def test_tc_sc_05_path_traversal_upload_image(admin_client, sample_category):
    """TC-SC-05: Upload dengan nama file traversal ../../x.png disimpan dengan UUID aman (P1)."""
    # Buat image buffer valid
    img_byte_arr = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    resp = admin_client.post(
        "/admin/products",
        data={
            "sku": "IMG-TEST-01",
            "name": "Produk Gambar",
            "category_id": str(sample_category["_id"]),
            "price": "15000",
            "stock": "10",
            "image": (img_byte_arr, "../../../evil_traversal.png"),
        },
    )
    assert resp.status_code == 302

    prod = product_repo.find_by_sku("IMG-TEST-01")
    assert prod is not None
    assert prod["image_url"] is not None
    assert "evil_traversal" not in prod["image_url"]
    assert prod["image_url"].startswith("/uploads/products/")

    # Verifikasi gambar tampil di halaman Beranda (/) dan Katalog (/products)
    r_home = admin_client.get("/")
    assert r_home.status_code == 200
    assert prod["image_url"].encode() in r_home.data

    r_cat = admin_client.get("/products")
    assert r_cat.status_code == 200
    assert prod["image_url"].encode() in r_cat.data


def test_home_uses_keyword_art_when_product_has_no_uploaded_image(client, sample_category):
    product_repo.insert(
        sku="VISUAL-TEST-01",
        name="Jus Jeruk 1 L",
        category_id=sample_category["_id"],
        price=16500,
        stock=12,
    )

    response = client.get("/")

    assert response.status_code == 200
    assert b"/static/images/products/juice.svg" in response.data


def test_home_renders_interactive_filters_for_categories_with_products(client, sample_category):
    product_repo.insert(
        sku="HOME-FILTER-TEST-01",
        name="Beras Interaktif 1 kg",
        category_id=sample_category["_id"],
        price=18000,
        stock=12,
    )

    response = client.get("/")

    assert response.status_code == 200
    assert b'data-home-filter="sembako"' in response.data
    assert b'data-category="sembako"' in response.data


def test_home_recommends_available_best_sellers_from_purchases(client, sample_category):
    best_seller_id = product_repo.insert(
        sku="HOME-RECOMMEND-BEST",
        name="Produk Rekomendasi Terlaris",
        category_id=sample_category["_id"],
        price=18000,
        stock=12,
    )
    product_repo.inc_sold_count(best_seller_id, 100)

    product_repo.insert(
        sku="HOME-RECOMMEND-NO-SALES",
        name="Produk Belum Terjual",
        category_id=sample_category["_id"],
        price=15000,
        stock=12,
    )
    out_of_stock_id = product_repo.insert(
        sku="HOME-RECOMMEND-UNAVAILABLE",
        name="Produk Terlaris Tidak Tersedia",
        category_id=sample_category["_id"],
        price=12000,
        stock=0,
    )
    product_repo.inc_sold_count(out_of_stock_id, 150)

    response = client.get("/")

    assert response.status_code == 200
    assert b'data-popular-float' in response.data
    recommendation_panel = response.data.split(b'<section class="popular-float-panel"', 1)[1].split(b"</section>", 1)[0]
    assert b"Produk Rekomendasi Terlaris" in recommendation_panel
    assert b"Produk Belum Terjual" not in recommendation_panel
    assert b"Produk Terlaris Tidak Tersedia" not in recommendation_panel


def test_home_shows_empty_state_when_catalog_has_no_active_products(client, monkeypatch):
    from app.services.catalog_service import catalog_service

    monkeypatch.setattr(catalog_service, "get_public_products", lambda **kwargs: ([], 0, 1))

    response = client.get("/")

    assert response.status_code == 200
    assert b"Belum ada produk aktif" in response.data


def test_catalog_only_shows_rating_when_reviews_exist(client, sample_category):
    pid = product_repo.insert(
        sku="RATING-TEST-01",
        name="Produk Rating Test",
        category_id=sample_category["_id"],
        price=12000,
        stock=10,
    )

    without_reviews = client.get("/products?q=RATING-TEST-01")
    assert without_reviews.status_code == 200
    assert b"product-card-rating" not in without_reviews.data

    product_repo.update_rating(pid, 4.5, 2)
    with_reviews = client.get("/products?q=RATING-TEST-01")
    assert with_reviews.status_code == 200
    assert b'aria-label="Rating 4.5 dari 5 berdasarkan 2 ulasan"' in with_reviews.data
    assert b"(2 ulasan)" in with_reviews.data


def test_product_detail_does_not_show_zero_rating_without_reviews(client, sample_category):
    pid = product_repo.insert(
        sku="NO-REVIEW-TEST",
        name="Produk Tanpa Ulasan",
        category_id=sample_category["_id"],
        price=12000,
        stock=10,
    )

    response = client.get(f"/products/{pid}")

    assert response.status_code == 200
    assert b"Belum ada ulasan untuk produk ini." in response.data
    assert b'class="review-score"' not in response.data
    assert b"NO-REVIEW-TEST" not in response.data
    assert b"Stok 10" not in response.data


def test_customer_catalog_hides_sku_and_exact_stock_but_marks_unavailable(client, sample_category):
    pid = product_repo.insert(
        sku="PRIVATE-CATALOG-01",
        name="Produk Tanpa Info Internal",
        category_id=sample_category["_id"],
        price=12000,
        stock=0,
    )

    catalog_response = client.get("/products?q=Produk%20Tanpa%20Info%20Internal")
    detail_response = client.get(f"/products/{pid}")

    assert catalog_response.status_code == 200
    assert b"PRIVATE-CATALOG-01" not in catalog_response.data
    assert b"Stok 0" not in catalog_response.data
    assert b"Tidak tersedia" in catalog_response.data
    assert detail_response.status_code == 200
    assert b"PRIVATE-CATALOG-01" not in detail_response.data
    assert b"Stok 0" not in detail_response.data
    assert b"Produk tidak tersedia saat ini" in detail_response.data


def test_admin_edit_product_form_post(admin_client, sample_category):
    """Admin mengedit produk melalui POST /admin/products/<id> termasuk unggah foto baru."""
    pid = product_repo.insert(
        sku="EDT-PROD-01",
        name="Produk Awal",
        category_id=sample_category["_id"],
        price=10000,
        stock=10,
        min_stock=2,
    )

    # Buat image buffer valid untuk edit
    img_byte_arr = io.BytesIO()
    img = Image.new("RGB", (80, 80), color="green")
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    # Edit via POST form dengan foto baru
    resp = admin_client.post(
        f"/admin/products/{pid}",
        data={
            "name": "Produk Diedit Sukses",
            "category_id": str(sample_category["_id"]),
            "price": "25000",
            "min_stock": "5",
            "description": "Deskripsi baru setelah diedit",
            "image": (img_byte_arr, "new_product_image.png"),
        },
    )
    assert resp.status_code == 302

    updated = product_repo.find_by_id(pid)
    assert updated["name"] == "Produk Diedit Sukses"
    assert updated["price"] == 25000
    assert updated["min_stock"] == 5
    assert updated["description"] == "Deskripsi baru setelah diedit"
    assert updated["stock"] == 10
    assert updated["image_url"] is not None
    assert updated["image_url"].startswith("/uploads/products/")

    # Edit lagi tanpa mengunggah foto baru (foto lama tetap utuh)
    old_img_url = updated["image_url"]
    resp_no_img = admin_client.post(
        f"/admin/products/{pid}",
        data={
            "name": "Produk Diedit Kedua",
            "category_id": str(sample_category["_id"]),
            "price": "30000",
            "min_stock": "5",
        },
    )
    assert resp_no_img.status_code == 302
    updated2 = product_repo.find_by_id(pid)
    assert updated2["name"] == "Produk Diedit Kedua"
    assert updated2["price"] == 30000
    assert updated2["image_url"] == old_img_url


