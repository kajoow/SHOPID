from io import BytesIO
from pathlib import Path

import pytest
from bson import ObjectId
from PIL import Image

from app.models.enums import UserRole
from app.repositories import user_repo
from app.utils.security import hash_password


def _login_customer(client):
    email = f"profile-{ObjectId()}@example.com"
    user_repo.insert(
        name="Pelanggan Profil",
        email=email,
        password_hash=hash_password("Password123!"),
        role=UserRole.USER,
    )
    response = client.post(
        "/auth/login",
        data={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 302
    return email


def _png_upload():
    image = BytesIO()
    Image.new("RGB", (4, 4), color=(40, 100, 70)).save(image, format="PNG")
    image.seek(0)
    return image


def test_profile_page_renders_account_features(client):
    _login_customer(client)

    response = client.get("/profile")

    assert response.status_code == 200
    assert b"Kelengkapan profil" in response.data
    assert b"Riwayat pesanan" in response.data
    assert b"Perbarui password" in response.data
    assert b"Ulangi password baru" in response.data
    assert b'aria-label="Belanja sekarang"' in response.data
    assert b'href="/wishlist">Wishlist' in response.data
    assert b'aria-label="Buka pencarian"' in response.data
    assert b'aria-label="Keranjang, 0 item"' in response.data


def test_customer_can_upload_profile_photo(client, app, monkeypatch, tmp_path):
    email = _login_customer(client)
    monkeypatch.setitem(app.config, "UPLOAD_DIR", str(tmp_path))

    response = client.post(
        "/profile/photo",
        data={"profile_image": (_png_upload(), "portrait.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    updated_user = user_repo.find_by_email(email)
    photo_url = updated_user["profile_image"]
    assert photo_url.startswith("/uploads/profiles/")
    assert (Path(tmp_path) / photo_url.removeprefix("/uploads/")).is_file()

    profile_page = client.get("/profile")
    assert photo_url.encode() in profile_page.data


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("portrait.gif", b"not-an-image", "Hanya format JPG dan PNG"),
        ("portrait.png", b"not-a-valid-png", "Berkas bukan gambar yang valid"),
    ],
)
def test_customer_cannot_upload_invalid_profile_photo(client, filename, content, message):
    email = _login_customer(client)

    response = client.post(
        "/profile/photo",
        data={"profile_image": (BytesIO(content), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert message.encode() in response.data
    assert "profile_image" not in user_repo.find_by_email(email)


def test_admin_cannot_upload_customer_profile_photo(client):
    email = f"admin-profile-{ObjectId()}@example.com"
    user_repo.insert(
        name="Admin Profil",
        email=email,
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
    )
    login_response = client.post(
        "/admin/login",
        data={"email": email, "password": "AdminPass123!"},
    )

    assert login_response.status_code == 302
    response = client.post(
        "/profile/photo",
        data={"profile_image": (_png_upload(), "portrait.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 403


def test_password_update_requires_matching_confirmation(client):
    email = _login_customer(client)
    original_hash = user_repo.find_by_email(email)["password_hash"]

    response = client.post(
        "/profile/password",
        data={
            "current_password": "Password123!",
            "new_password": "NewPassword123!",
            "confirm_password": "Different123!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 422
    assert b"Konfirmasi password tidak sama" in response.data
    assert user_repo.find_by_email(email)["password_hash"] == original_hash
