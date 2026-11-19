import pytest
from bson import ObjectId
from app.repositories import user_repo
from app.models.enums import UserRole
from app.utils.security import hash_password


def test_tc_au_01_registrasi_valid(client, db):
    """TC-AU-01: Registrasi valid -> Akun dibuat, role user, redirect login (P1)."""
    resp = client.post(
        "/auth/register",
        data={
            "name": "User Baru",
            "email": "userbaru@example.com",
            "password": "Password123!",
            "phone": "081234567899",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]

    user = user_repo.find_by_email("userbaru@example.com")
    assert user is not None
    assert user["role"] == UserRole.USER
    assert user["name"] == "User Baru"
    assert user["is_active"] is True


def test_tc_au_02_email_sudah_terdaftar(client, db):
    """TC-AU-02: Email sudah terdaftar (beda huruf besar/kecil) -> 409 (P1)."""
    resp = client.post(
        "/auth/register",
        data={
            "name": "User Duplikat",
            "email": "USERBARU@example.com",  # Huruf besar
            "password": "Password123!",
        },
    )
    assert resp.status_code == 409


def test_tc_au_03_email_password_tidak_valid(client):
    """TC-AU-03: Email/password tidak valid -> 422 (P1)."""
    # Email tanpa @
    resp = client.post(
        "/auth/register",
        data={"name": "Test", "email": "tanpa-at", "password": "Password123!"},
    )
    assert resp.status_code == 422

    # Password terlalu pendek (< 8 karakter)
    resp2 = client.post(
        "/auth/register",
        data={"name": "Test", "email": "valid@example.com", "password": "short"},
    )
    assert resp2.status_code == 422


def test_tc_au_04_upaya_injeksi_role(client, db):
    """TC-AU-04: Upaya injeksi role via form -> Akun dibuat sebagai role 'user', role dari form diabaikan (P1)."""
    resp = client.post(
        "/auth/register",
        data={
            "name": "Attacker",
            "email": "attacker@example.com",
            "password": "Password123!",
            "role": "admin",  # Percobaan injeksi role admin
        },
    )
    assert resp.status_code == 302
    user = user_repo.find_by_email("attacker@example.com")
    assert user is not None
    assert user["role"] == UserRole.USER


def test_tc_au_05_password_di_hash_argon2id(client, db):
    """TC-AU-05: Password di-hash Argon2id, diawali $argon2id$ dan bukan plaintext (P1)."""
    user = user_repo.find_by_email("userbaru@example.com")
    assert user["password_hash"].startswith("$argon2id$")
    assert "Password123!" not in user["password_hash"]


def test_tc_au_06_login_valid(client, db):
    """TC-AU-06: Login valid -> Session dibuat, redirect sesuai role (P1)."""
    resp = client.post(
        "/auth/login",
        data={"email": "userbaru@example.com", "password": "Password123!"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "user_id" in sess
        assert sess["role"] == UserRole.USER


def test_admin_and_customer_login_use_separate_routes(client, db):
    """Akun admin and pelanggan hanya dapat login lewat portal masing-masing."""
    user_repo.insert(
        name="Admin Portal",
        email="admin-portal@example.com",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
    )
    user_repo.insert(
        name="Customer Portal",
        email="customer-portal@example.com",
        password_hash=hash_password("UserPass123!"),
        role=UserRole.USER,
    )

    admin_on_customer_route = client.post(
        "/auth/login",
        data={"email": "admin-portal@example.com", "password": "AdminPass123!"},
    )
    assert admin_on_customer_route.status_code == 401
    with client.session_transaction() as sess:
        assert "user_id" not in sess

    customer_on_admin_route = client.post(
        "/admin/login",
        data={"email": "customer-portal@example.com", "password": "UserPass123!"},
    )
    assert customer_on_admin_route.status_code == 401
    with client.session_transaction() as sess:
        assert "user_id" not in sess

    admin_login_page = client.get("/admin/login")
    assert admin_login_page.status_code == 200
    assert b"Masuk ke panel admin" in admin_login_page.data

    admin_login = client.post(
        "/admin/login",
        data={"email": "admin-portal@example.com", "password": "AdminPass123!"},
    )
    assert admin_login.status_code == 302
    assert "/admin/dashboard" in admin_login.headers["Location"]
    with client.session_transaction() as sess:
        assert sess["role"] == UserRole.ADMIN


def test_tc_au_07_pesan_galat_login_generik(client):
    """TC-AU-07: Password salah vs email tidak ada -> Pesan galat identik generik 401 (P1)."""
    # Email tidak ada
    resp_no_email = client.post(
        "/auth/login",
        data={"email": "nonexistent@example.com", "password": "Password123!"},
    )
    assert resp_no_email.status_code == 401
    assert b"Email atau password salah" in resp_no_email.data

    # Email ada, password salah
    resp_wrong_pwd = client.post(
        "/auth/login",
        data={"email": "userbaru@example.com", "password": "WrongPassword123!"},
    )
    assert resp_wrong_pwd.status_code == 401
    assert b"Email atau password salah" in resp_wrong_pwd.data


def test_tc_au_08_akun_nonaktif(client, db):
    """TC-AU-08: Akun nonaktif (is_active=false) -> Login ditolak (P2)."""
    # Buat user nonaktif
    uid = user_repo.insert(
        name="User Blokir",
        email="blocked@example.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.USER,
        is_active=False,
    )
    resp = client.post(
        "/auth/login",
        data={"email": "blocked@example.com", "password": "Password123!"},
    )
    assert resp.status_code in [401, 403]


def test_tc_au_10_logout(client):
    """TC-AU-10: Logout -> POST /auth/logout lalu akses /cart -> redirect login (P1)."""
    # Login dulu
    client.post("/auth/login", data={"email": "userbaru@example.com", "password": "Password123!"})
    # Logout
    resp_logout = client.post("/auth/logout")
    assert resp_logout.status_code == 302

    # Akses /cart
    resp_cart = client.get("/cart")
    assert resp_cart.status_code == 302
    assert "/auth/login" in resp_cart.headers["Location"]


def test_tc_au_11_session_fixation(client):
    """TC-AU-11: ID sesi berubah saat login berhasil (P2)."""
    client.get("/")
    # Ambil session cookie sebelum login
    cookies_before = client.get_cookie("session")

    # Login
    client.post("/auth/login", data={"email": "userbaru@example.com", "password": "Password123!"})
    cookies_after = client.get_cookie("session")

    assert cookies_before != cookies_after


def test_tc_rb_01_user_akses_rute_admin_ditolak(client):
    """TC-RB-01: User mengakses rute admin -> 403 Forbidden (P1)."""
    # Login sebagai user
    client.post("/auth/login", data={"email": "userbaru@example.com", "password": "Password123!"})

    resp = client.get("/admin/dashboard")
    assert resp.status_code == 403


def test_tc_rb_02_anonim_akses_rute_user(client):
    """TC-RB-02: Anonim mengakses rute user -> 302 ke login (P1)."""
    client.post("/auth/logout")  # Pastikan logout
    resp = client.get("/cart")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_anonymous_admin_route_redirects_to_admin_login(client):
    response = client.get("/admin/dashboard")
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_tc_rb_03_admin_akses_rute_pelanggan_ditolak(client, db):
    """TC-RB-03: Admin mengakses rute pelanggan -> 403 (keputusan D8) (P2)."""
    # Buat admin
    admin_id = user_repo.insert(
        name="Admin Test",
        email="admintest@example.com",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
    )
    # Login sebagai admin
    client.post("/admin/login", data={"email": "admintest@example.com", "password": "AdminPass123!"})

    # Coba akses rute keranjang pelanggan
    resp = client.post("/cart/items", json={"product_id": str(ObjectId()), "quantity": 1})
    assert resp.status_code == 403


def test_tc_rb_07_hanya_dua_role_validasi(db):
    """TC-RB-07: Hanya dua role valid (user / admin). Simpan role lain ditolak oleh $jsonSchema (P1)."""
    with pytest.raises(Exception):
        db.users.insert_one({
            "name": "Manager",
            "email": "manager@example.com",
            "password_hash": "$argon2id$...",
            "role": "manager",  # Tidak diizinkan oleh enum schema
            "is_active": True,
            "created_at": "2026-11-16T00:00:00Z",
        })


def test_tc_sc_04_session_cookie_security(app, client):
    """TC-SC-04: Cookie sesi memiliki HttpOnly dan SameSite (P1)."""
    resp = client.post("/auth/login", data={"email": "userbaru@example.com", "password": "Password123!"})
    cookie = client.get_cookie("session")
    assert cookie is not None
    assert cookie.http_only is True
    assert cookie.same_site == "Lax"


def test_tc_sc_09_hash_tidak_bocor_di_json(client):
    """TC-SC-09: password_hash tidak pernah dikembalikan dalam response JSON (P1)."""
    # Login sebagai user
    client.post("/auth/login", data={"email": "userbaru@example.com", "password": "Password123!"})
    # Update profile via PATCH (mengembalikan JSON)
    resp = client.patch("/profile", json={"name": "Nama Baru Update"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "password_hash" not in data.get("data", {})
