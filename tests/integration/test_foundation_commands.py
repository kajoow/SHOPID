from unittest.mock import patch
from app.commands import init_db_command, create_admin_command, seed_demo_command
from app.repositories import user_repo, product_repo, category_repo, audit_repo
from app.models.enums import UserRole


def test_init_db_cli(app, db):
    runner = app.test_cli_runner()
    result = runner.invoke(init_db_command)
    assert result.exit_code == 0
    assert "Inisialisasi database selesai" in result.output
    colls = db.list_collection_names()
    assert "master_product" in colls
    assert "users" in colls
    assert "orders" in colls


def test_create_admin_cli(app, db):
    runner = app.test_cli_runner()
    # Simulasikan input: name, email, password, confirm_password
    with patch("builtins.input", side_effect=["Admin Utama", "superadmin@example.com"]), \
         patch("getpass.getpass", side_effect=["AdminPass123!", "AdminPass123!"]):
        result = runner.invoke(create_admin_command)
        assert result.exit_code == 0
        assert "berhasil dibuat" in result.output

    # Cek user di repo
    admin = user_repo.find_by_email("superadmin@example.com")
    assert admin is not None
    assert admin["role"] == UserRole.ADMIN
    assert admin["password_hash"].startswith("$argon2id$")

    # Cek audit log
    logs = audit_repo.find_all({"entity_type": "users", "action": "user.bootstrap_admin"})
    assert len(logs) >= 1


def test_seed_demo_cli(app, db):
    runner = app.test_cli_runner()
    result = runner.invoke(seed_demo_command)
    assert result.exit_code == 0
    assert "Pengisian data demo selesai dengan sukses" in result.output

    # Cek produk
    prod = product_repo.find_by_sku("MNM-0001")
    assert prod is not None
    assert prod["price"] == 3500
    assert prod["stock"] == 120
    assert product_repo.find_by_sku("MKN-0006")["name"] == "Keripik Singkong Balado 160 g"
    assert product_repo.find_by_sku("MNM-0008")["name"] == "Teh Botol 350 ml"
    assert product_repo.find_by_sku("MKN-0009")["name"] == "Makaroni Pedas 120 g"
    assert product_repo.find_by_sku("RTG-0010")["name"] == "Pembersih Lantai 800 ml"
    assert product_repo.find_by_sku("PWD-0011")["name"] == "Deodoran Roll On 50 ml"

    # Cek user demo
    budi = user_repo.find_by_email("budi@example.com")
    assert budi is not None
    assert budi["role"] == UserRole.USER

