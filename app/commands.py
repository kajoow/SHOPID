"""CLI commands untuk RetailBrain: init-db, create-admin, seed-demo (Bab 11.6, 16.3, 20)."""
import getpass
import secrets
from datetime import datetime, timezone, timedelta
import click
from flask import current_app
from flask.cli import with_appcontext
from bson import ObjectId

from .extensions import get_db
from .models.schemas import COLLECTIONS
from .models.enums import UserRole, StockMovementType, StockReferenceType, DiscountType
from .utils.security import hash_password
from .utils.validators import validate_email, validate_password, validate_string, validate_phone, ValidationError
from .repositories import (
    user_repo,
    category_repo,
    product_repo,
    stock_repo,
    promotion_repo,
    audit_repo,
)


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Membuat 11 koleksi MongoDB dengan validasi $jsonSchema dan seluruh indeks (Bab 11.6)."""
    db = get_db()
    existing_collections = set(db.list_collection_names())

    click.echo("Menginisialisasi koleksi MongoDB...")
    for col_name, schema in COLLECTIONS.items():
        if col_name not in existing_collections:
            db.create_collection(col_name, validator=schema)
            click.echo(f"  [+] Koleksi '{col_name}' dibuat dengan validator $jsonSchema.")
        else:
            try:
                db.command("collMod", col_name, validator=schema)
                click.echo(f"  [*] Validator koleksi '{col_name}' diperbarui.")
            except Exception as e:
                click.echo(f"  [!] Gagal collMod '{col_name}': {e}")

    click.echo("\nMembuat seluruh indeks sesuai Bab 11.6...")

    # 1. users
    db.users.create_index([("email", 1)], unique=True)

    # 2. master_product
    db.master_product.create_index([("sku", 1)], unique=True)
    db.master_product.create_index([("category_id", 1), ("is_active", 1), ("price", 1)])
    db.master_product.create_index([("name", "text")])
    db.master_product.create_index([("sold_count", -1)])

    # 3. categories
    db.categories.create_index([("slug", 1)], unique=True)
    db.categories.create_index([("name", 1)], unique=True)

    # 4. carts
    db.carts.create_index([("user_id", 1)], unique=True)

    # 5. orders
    db.orders.create_index([("order_number", 1)], unique=True)
    db.orders.create_index([("user_id", 1), ("created_at", -1)])
    db.orders.create_index([("order_status", 1), ("created_at", -1)])
    db.orders.create_index([("payment_status", 1)])
    db.orders.create_index([("idempotency_key", 1)], unique=True)

    # 6. stock_movements
    db.stock_movements.create_index([("product_id", 1), ("created_at", -1)])
    db.stock_movements.create_index([("reference_type", 1), ("reference_id", 1)])

    # 7. promotions
    db.promotions.create_index([("code", 1)], unique=True)

    # 8. wishlists
    db.wishlists.create_index([("user_id", 1)], unique=True)

    # 9. reviews
    db.reviews.create_index([("product_id", 1), ("is_visible", 1), ("created_at", -1)])
    db.reviews.create_index([("user_id", 1), ("product_id", 1), ("order_id", 1)], unique=True)

    # 10. notifications
    db.notifications.create_index([("user_id", 1), ("is_read", 1), ("created_at", -1)])

    # 11. audit_logs
    db.audit_logs.create_index([("created_at", -1)])
    db.audit_logs.create_index([("entity_type", 1), ("entity_id", 1)])
    db.audit_logs.create_index([("actor_id", 1)])

    click.echo("Inisialisasi database selesai: tepat 11 koleksi dan seluruh indeks aktif.")


@click.command("create-admin")
@with_appcontext
def create_admin_command():
    """Bootstrap akun admin pertama secara interaktif (Bab 16.3)."""
    allow_bootstrap = current_app.config.get("ALLOW_ADMIN_BOOTSTRAP", True)
    if not allow_bootstrap:
        click.echo("Error: ALLOW_ADMIN_BOOTSTRAP bernilai false. Prosedur bootstrap admin dinonaktifkan.", err=True)
        return

    click.echo("=== Bootstrap Admin RetailBrain ===")
    try:
        raw_name = input("Nama admin: ")
        name = validate_string(raw_name, min_len=2, max_len=100, field_name="Nama admin")

        raw_email = input("Email admin: ")
        email = validate_email(raw_email)

        # Cek apakah email sudah ada
        existing = user_repo.find_by_email(email)
        if existing:
            click.echo(f"Error: Email '{email}' sudah terdaftar.", err=True)
            return

        password = getpass.getpass("Password (min 8 karakter, huruf + angka): ")
        password = validate_password(password)

        confirm_pwd = getpass.getpass("Konfirmasi password: ")
        if password != confirm_pwd:
            click.echo("Error: Konfirmasi password tidak cocok.", err=True)
            return

    except ValidationError as e:
        click.echo(f"Validasi gagal: {e.message}", err=True)
        return
    except Exception as e:
        click.echo(f"Terjadi kesalahan input: {e}", err=True)
        return

    # Hash dengan Argon2id
    pwd_hash = hash_password(password)

    # Simpan user dengan role admin
    admin_id = user_repo.insert(
        name=name,
        email=email,
        password_hash=pwd_hash,
        role=UserRole.ADMIN,
        is_active=True,
    )

    # Tulis audit log user.bootstrap_admin
    audit_repo.log(
        actor_id=admin_id,
        action="user.bootstrap_admin",
        entity_type="users",
        entity_id=admin_id,
        before=None,
        after={"email": email, "role": UserRole.ADMIN, "name": name},
    )

    click.echo(f"Admin '{email}' berhasil dibuat dengan ID: {admin_id}")
    click.echo("Catatan: Di produksi, segera ubah ALLOW_ADMIN_BOOTSTRAP=false di file .env.")


@click.command("seed-demo")
@with_appcontext
def seed_demo_command():
    """Mengisi data awal demo: kategori, produk, voucher, dan user (Bab 1.1, 23.2)."""
    click.echo("Memulai pengisian data demo...")

    # 1. Kategori
    demo_categories = [
        {"name": "Minuman", "slug": "minuman", "description": "Air mineral, teh, kopi, dan minuman kemasan"},
        {"name": "Makanan Ringan", "slug": "makanan-ringan", "description": "Biskuit, keripik, dan camilan harian"},
        {"name": "Kebutuhan Rumah Tangga", "slug": "rumah-tangga", "description": "Perlengkapan kebersihan dan kebutuhan harian"},
        {"name": "Perawatan Diri", "slug": "perawatan-diri", "description": "Sabun, sampo, dan perawatan tubuh"},
    ]

    cat_map = {}
    for cat in demo_categories:
        existing = category_repo.find_by_slug(cat["slug"])
        if not existing:
            cid = category_repo.insert(
                name=cat["name"],
                slug=cat["slug"],
                description=cat["description"],
                is_active=True,
            )
            cat_map[cat["slug"]] = cid
            click.echo(f"  [+] Kategori '{cat['name']}' dibuat.")
        else:
            cat_map[cat["slug"]] = existing["_id"]
            click.echo(f"  [*] Kategori '{cat['name']}' sudah ada.")

    # 2. User Demo
    demo_password_env = current_app.config.get("DEMO_PASSWORD")
    if demo_password_env:
        demo_pwd = demo_password_env
    else:
        demo_pwd = secrets.token_urlsafe(12) + "A1!"
        click.echo(f"\n=======================================================")
        click.echo(f"PASSWORD USER DEMO DIHASILKAN SECARA ACAK:")
        click.echo(f"{demo_pwd}")
        click.echo(f"Simpan password ini untuk demonstrasi dan pengujian.")
        click.echo(f"=======================================================\n")

    demo_users = [
        {
            "name": "Admin Toko Demo",
            "email": "admin@retailbrain.example",
            "role": UserRole.ADMIN,
            "phone": None,
            "address": None,
        },
        {
            "name": "Budi Santoso",
            "email": "budi@example.com",
            "role": UserRole.USER,
            "phone": "081234567890",
            "address": "Jl. Melati No. 10, Kota Contoh",
        },
        {
            "name": "Sari Wijaya",
            "email": "sari@example.com",
            "role": UserRole.USER,
            "phone": "081298765432",
            "address": "Jl. Anggrek No. 5, Kota Contoh",
        },
    ]

    user_map = {}
    pwd_hash = hash_password(demo_pwd)

    for u in demo_users:
        existing = user_repo.find_by_email(u["email"])
        if not existing:
            uid = user_repo.insert(
                name=u["name"],
                email=u["email"],
                password_hash=pwd_hash,
                role=u["role"],
                phone=u["phone"],
                address=u["address"],
                is_active=True,
            )
            user_map[u["email"]] = uid
            audit_repo.log(
                actor_id=uid,
                action="user.seed_demo",
                entity_type="users",
                entity_id=uid,
                after={"email": u["email"], "role": u["role"]},
            )
            click.echo(f"  [+] User demo '{u['email']}' ({u['role']}) dibuat.")
        else:
            user_map[u["email"]] = existing["_id"]
            click.echo(f"  [*] User demo '{u['email']}' sudah ada.")

    admin_actor_id = user_map.get("admin@retailbrain.example") or ObjectId()

    # 3. Produk Demo
    demo_products = [
        {
            "sku": "MNM-0001",
            "name": "Air Mineral 600 ml",
            "cat_slug": "minuman",
            "price": 3500,
            "stock": 120,
            "min_stock": 24,
            "description": "Air mineral kemasan botol 600 ml higienis dan segar.",
        },
        {
            "sku": "RTG-0007",
            "name": "Deterjen Bubuk 800 g",
            "cat_slug": "rumah-tangga",
            "price": 18500,
            "stock": 40,
            "min_stock": 10,
            "description": "Deterjen konsentrat untuk pencucian pakaian harian.",
        },
        {
            "sku": "MNM-0002",
            "name": "Teh Celup 25 pcs",
            "cat_slug": "minuman",
            "price": 9800,
            "stock": 50,
            "min_stock": 10,
            "description": "Teh hitam celup aroma melati alami.",
        },
        {
            "sku": "MKN-0003",
            "name": "Biskuit Gandum 200 g",
            "cat_slug": "makanan-ringan",
            "price": 12000,
            "stock": 30,
            "min_stock": 8,
            "description": "Biskuit gandum renyah kaya serat.",
        },
        {
            "sku": "PWD-0005",
            "name": "Sabun Mandi Cair 450 ml",
            "cat_slug": "perawatan-diri",
            "price": 24000,
            "stock": 25,
            "min_stock": 5,
            "description": "Sabun mandi cair antibakterial wangi segar.",
        },
        {
            "sku": "MNM-0004",
            "name": "Kopi Instan 100 g",
            "cat_slug": "minuman",
            "price": 14500,
            "stock": 15,
            "min_stock": 5,
            "description": "Kopi bubuk instan robusta pilihan.",
        },
        {
            "sku": "MNM-0005",
            "name": "Jus Jeruk 1 L",
            "cat_slug": "minuman",
            "price": 16500,
            "stock": 36,
            "min_stock": 8,
            "description": "Minuman rasa jeruk dalam kemasan 1 liter.",
        },
        {
            "sku": "MKN-0006",
            "name": "Keripik Singkong Balado 160 g",
            "cat_slug": "makanan-ringan",
            "price": 10000,
            "stock": 42,
            "min_stock": 10,
            "description": "Keripik singkong renyah dengan bumbu balado.",
        },
        {
            "sku": "RTG-0008",
            "name": "Tisu Wajah 250 sheets",
            "cat_slug": "rumah-tangga",
            "price": 16500,
            "stock": 40,
            "min_stock": 8,
            "description": "Tisu wajah lembut untuk kebutuhan sehari-hari.",
        },
        {
            "sku": "PWD-0009",
            "name": "Pasta Gigi Herbal 120 g",
            "cat_slug": "perawatan-diri",
            "price": 12500,
            "stock": 36,
            "min_stock": 8,
            "description": "Pasta gigi dengan ekstrak herbal untuk perawatan gigi harian.",
        },
        {
            "sku": "MNM-0006",
            "name": "Susu UHT 1 L",
            "cat_slug": "minuman",
            "price": 18500,
            "stock": 32,
            "min_stock": 8,
            "description": "Susu UHT dalam kemasan 1 liter.",
        },
        {
            "sku": "MNM-0007",
            "name": "Kopi Susu Kaleng 240 ml",
            "cat_slug": "minuman",
            "price": 8500,
            "stock": 48,
            "min_stock": 12,
            "description": "Minuman kopi susu siap minum dalam kemasan kaleng.",
        },
        {
            "sku": "MNM-0008",
            "name": "Teh Botol 350 ml",
            "cat_slug": "minuman",
            "price": 5500,
            "stock": 60,
            "min_stock": 15,
            "description": "Teh siap minum dalam botol 350 ml.",
        },
        {
            "sku": "MKN-0007",
            "name": "Wafer Cokelat 150 g",
            "cat_slug": "makanan-ringan",
            "price": 11000,
            "stock": 38,
            "min_stock": 9,
            "description": "Wafer renyah berlapis krim cokelat.",
        },
        {
            "sku": "MKN-0008",
            "name": "Kacang Panggang 100 g",
            "cat_slug": "makanan-ringan",
            "price": 9000,
            "stock": 45,
            "min_stock": 10,
            "description": "Kacang panggang gurih dalam kemasan 100 g.",
        },
        {
            "sku": "MKN-0009",
            "name": "Makaroni Pedas 120 g",
            "cat_slug": "makanan-ringan",
            "price": 7500,
            "stock": 50,
            "min_stock": 12,
            "description": "Camilan makaroni renyah dengan bumbu pedas.",
        },
        {
            "sku": "RTG-0009",
            "name": "Sabun Cuci Piring 700 ml",
            "cat_slug": "rumah-tangga",
            "price": 14000,
            "stock": 30,
            "min_stock": 7,
            "description": "Sabun cuci piring cair untuk kebutuhan dapur.",
        },
        {
            "sku": "RTG-0010",
            "name": "Pembersih Lantai 800 ml",
            "cat_slug": "rumah-tangga",
            "price": 17500,
            "stock": 28,
            "min_stock": 7,
            "description": "Pembersih lantai cair dengan aroma segar.",
        },
        {
            "sku": "PWD-0010",
            "name": "Sampo Anti Ketombe 170 ml",
            "cat_slug": "perawatan-diri",
            "price": 22000,
            "stock": 26,
            "min_stock": 6,
            "description": "Sampo perawatan rambut dalam kemasan 170 ml.",
        },
        {
            "sku": "PWD-0011",
            "name": "Deodoran Roll On 50 ml",
            "cat_slug": "perawatan-diri",
            "price": 16000,
            "stock": 24,
            "min_stock": 6,
            "description": "Deodoran roll-on ukuran 50 ml.",
        },
    ]

    for p in demo_products:
        existing = product_repo.find_by_sku(p["sku"])
        cat_id = cat_map.get(p["cat_slug"])
        if not existing and cat_id:
            pid = product_repo.insert(
                sku=p["sku"],
                name=p["name"],
                category_id=cat_id,
                price=p["price"],
                stock=p["stock"],
                min_stock=p["min_stock"],
                description=p["description"],
                is_active=True,
            )
            # Inisialisasi stock_movements 'initial' sesuai Bab 7.F
            if p["stock"] > 0:
                stock_repo.insert(
                    product_id=pid,
                    movement_type=StockMovementType.INITIAL,
                    quantity=p["stock"],
                    before_stock=0,
                    after_stock=p["stock"],
                    reference_type=StockReferenceType.PRODUCT_CREATE,
                    reference_id=pid,
                    actor_id=admin_actor_id,
                    note="Initial seed demo",
                )
            audit_repo.log(
                actor_id=admin_actor_id,
                action="product.create",
                entity_type="master_product",
                entity_id=pid,
                after={"sku": p["sku"], "name": p["name"], "stock": p["stock"], "price": p["price"]},
            )
            click.echo(f"  [+] Produk demo '{p['name']}' ({p['sku']}) dibuat dengan stok {p['stock']}.")
        else:
            click.echo(f"  [*] Produk '{p['sku']}' sudah ada.")

    # 4. Promotions Demo (Bab 12.7)
    now = datetime.now(timezone.utc)
    demo_promos = [
        {
            "code": "HEMAT10",
            "discount_type": DiscountType.PERCENTAGE,
            "value": 10,
            "min_order": 50000,
            "max_discount": 15000,
            "quota": 100,
            "used_count": 0,
            "starts_at": now - timedelta(days=1),
            "ends_at": now + timedelta(days=30),
            "is_active": True,
        },
        {
            "code": "POTONG10K",
            "discount_type": DiscountType.FIXED,
            "value": 10000,
            "min_order": 40000,
            "max_discount": None,
            "quota": 50,
            "used_count": 0,
            "starts_at": now - timedelta(days=1),
            "ends_at": now + timedelta(days=30),
            "is_active": True,
        },
    ]

    for pr in demo_promos:
        existing = promotion_repo.find_by_code(pr["code"])
        if not existing:
            pr_id = promotion_repo.insert(pr)
            audit_repo.log(
                actor_id=admin_actor_id,
                action="promotion.create",
                entity_type="promotions",
                entity_id=pr_id,
                after={"code": pr["code"], "discount_type": pr["discount_type"]},
            )
            click.echo(f"  [+] Voucher '{pr['code']}' dibuat.")
        else:
            click.echo(f"  [*] Voucher '{pr['code']}' sudah ada.")

    click.echo("\nPengisian data demo selesai dengan sukses!")

