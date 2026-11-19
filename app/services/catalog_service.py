"""Catalog service: Logika bisnis produk, kategori, pencarian, dan soft delete (Bab 7.B, 14.3, 14.5)."""
import re
from bson import ObjectId
from flask import abort
from werkzeug.datastructures import FileStorage

from ..repositories import product_repo, category_repo, stock_repo, audit_repo
from ..models.enums import StockMovementType, StockReferenceType
from ..utils.validators import (
    validate_string,
    validate_int,
    validate_object_id,
    ValidationError,
)
from ..utils.uploads import save_upload_image
from .auth_service import ConflictError


class CatalogService:
    def get_public_products(
        self,
        q: str | None = None,
        category_slug: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        sort: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list, int, int]:
        """Katalog publik: hanya menampilkan produk aktif, mendukung filter, search, sort, dan paginasi (Bab 7.B)."""
        query = {"is_active": True}

        # 1. Filter Kategori berdasarkan slug
        if category_slug:
            cat = category_repo.find_by_slug(category_slug)
            if not cat or not cat.get("is_active", True):
                return [], 0, 1
            query["category_id"] = cat["_id"]

        # 2. Pencarian aman (re.escape, max 60 chars) cocok name (regex) atau SKU (persis) (TC-PR-07..09)
        if q:
            clean_q = validate_string(q, min_len=1, max_len=60, field_name="Pencarian")
            safe_regex = re.escape(clean_q)
            query["$or"] = [
                {"name": {"$regex": safe_regex, "$options": "i"}},
                {"sku": clean_q.upper()},
            ]

        # 3. Filter Rentang Harga
        price_conditions = {}
        if min_price is not None:
            price_conditions["$gte"] = validate_int(min_price, min_val=0, field_name="Harga minimum")
        if max_price is not None:
            price_conditions["$lte"] = validate_int(max_price, min_val=0, field_name="Harga maksimum")
        if price_conditions:
            query["price"] = price_conditions

        # 4. Sorting (price_asc, price_desc, popular, default terbaru) (Bab 7.B)
        if sort == "price_asc":
            sort_criteria = [("price", 1)]
        elif sort == "price_desc":
            sort_criteria = [("price", -1)]
        elif sort == "popular":
            sort_criteria = [("sold_count", -1)]
        else:
            sort_criteria = [("created_at", -1)]

        # 5. Paginasi: default 20, dibatasi maksimum 50 (TC-PR-12)
        safe_page = max(1, validate_int(page, min_val=1, field_name="Halaman"))
        safe_limit = min(50, max(1, validate_int(per_page, min_val=1, field_name="Item per halaman")))
        skip = (safe_page - 1) * safe_limit

        products = product_repo.find_all(query, sort_criteria, skip=skip, limit=safe_limit)
        total_count = product_repo.count(query)
        total_pages = (total_count + safe_limit - 1) // safe_limit if total_count > 0 else 1

        return products, total_count, total_pages

    def get_best_selling_products(self, limit: int = 3) -> list:
        return product_repo.find_all(
            {"is_active": True, "stock": {"$gt": 0}, "sold_count": {"$gt": 0}},
            [("sold_count", -1), ("created_at", -1)],
            limit=limit,
        )

    def get_product_detail(self, product_id_input: any) -> dict:
        """Ambil detail produk aktif. ObjectId tidak valid atau produk nonaktif = 404 (TC-VA-01, TC-PR-05)."""
        pid = validate_object_id(product_id_input, field_name="ID Produk")
        prod = product_repo.find_by_id(pid)
        if not prod or not prod.get("is_active", True):
            abort(404, description="Produk tidak ditemukan atau sudah dinonaktifkan")
        return prod

    def create_product(
        self,
        sku: str,
        name: str,
        category_id_input: any,
        price_input: any,
        stock_input: any = 0,
        min_stock_input: any = 5,
        description: str | None = None,
        image_file: FileStorage | None = None,
        actor_id: ObjectId | None = None,
    ) -> ObjectId:
        """Admin: membuat produk baru (+ stok awal initial) (Bab 14.5 & TC-PR-01..04)."""
        # Validasi SKU
        valid_sku = validate_string(sku, min_len=3, max_len=32, field_name="SKU").upper()
        if not re.match(r"^[A-Z0-9-]{3,32}$", valid_sku):
            raise ValidationError("Format SKU harus berupa huruf besar, angka, dan tanda hubung (-)", field="sku")

        # Cek keunikan SKU
        if product_repo.find_by_sku(valid_sku):
            raise ConflictError(f"SKU '{valid_sku}' sudah terdaftar.")

        # Validasi nama & deskripsi
        valid_name = validate_string(name, min_len=2, max_len=150, field_name="Nama produk")
        valid_desc = validate_string(description, min_len=0, max_len=2000, field_name="Deskripsi") if description else None

        # Validasi kategori
        cat_id = validate_object_id(category_id_input, field_name="Kategori")
        cat = category_repo.find_by_id(cat_id)
        if not cat:
            raise ValidationError("Kategori yang dipilih tidak ditemukan", field="category_id")

        # Validasi harga & stok
        valid_price = validate_int(price_input, min_val=1, field_name="Harga")
        valid_stock = validate_int(stock_input, min_val=0, field_name="Stok awal")
        valid_min_stock = validate_int(min_stock_input, min_val=0, field_name="Stok minimum")

        # Upload gambar jika disertakan
        image_url = None
        if image_file and image_file.filename:
            image_url = save_upload_image(image_file, subfolder="products")

        # Insert produk ke master_product
        pid = product_repo.insert(
            sku=valid_sku,
            name=valid_name,
            category_id=cat_id,
            price=valid_price,
            stock=valid_stock,
            min_stock=valid_min_stock,
            description=valid_desc,
            image_url=image_url,
            is_active=True,
        )

        # Inisialisasi stock_movements jika stok awal > 0 (Bab 7.F & TC-PR-01)
        if valid_stock > 0 and actor_id:
            stock_repo.insert(
                product_id=pid,
                movement_type=StockMovementType.INITIAL,
                quantity=valid_stock,
                before_stock=0,
                after_stock=valid_stock,
                reference_type=StockReferenceType.PRODUCT_CREATE,
                reference_id=pid,
                actor_id=actor_id,
                note="Inisialisasi stok produk baru",
            )

        # Audit log
        if actor_id:
            audit_repo.log(
                actor_id=actor_id,
                action="product.create",
                entity_type="master_product",
                entity_id=pid,
                after={"sku": valid_sku, "name": valid_name, "price": valid_price, "stock": valid_stock},
            )

        return pid

    def update_product(
        self,
        product_id_input: any,
        updates_data: dict,
        image_file: any = None,
        actor_id: ObjectId | None = None,
    ) -> bool:
        """Admin: update produk. Perubahan stok DITOLAK (harus lewat inventori) (Bab 14.5 & TC-PR-06)."""
        pid = validate_object_id(product_id_input, field_name="ID Produk")
        existing = product_repo.find_by_id(pid)
        if not existing:
            abort(404, description="Produk tidak ditemukan")

        # Cegah perubahan stok lewat PATCH produk (TC-PR-06)
        if "stock" in updates_data and updates_data["stock"] not in [None, ""]:
            raise ValidationError("Stok produk tidak boleh diubah langsung lewat rute produk. Gunakan fitur inventori.", field="stock")

        allowed_fields = {"name", "price", "min_stock", "description", "category_id", "is_active", "image_url"}
        sanitized = {}
        before_state = {}

        for k, v in updates_data.items():
            if k not in allowed_fields:
                continue

            if k == "name":
                sanitized[k] = validate_string(v, min_len=2, max_len=150, field_name="Nama produk")
            elif k == "price":
                sanitized[k] = validate_int(v, min_val=1, field_name="Harga")
            elif k == "min_stock":
                sanitized[k] = validate_int(v, min_val=0, field_name="Stok minimum")
            elif k == "description":
                sanitized[k] = validate_string(v, min_len=0, max_len=2000, field_name="Deskripsi") if v else None
            elif k == "category_id":
                cid = validate_object_id(v, field_name="Kategori")
                if not category_repo.find_by_id(cid):
                    raise ValidationError("Kategori tidak valid", field="category_id")
                sanitized[k] = cid
            elif k == "is_active":
                sanitized[k] = bool(v)
            elif k == "image_url":
                sanitized[k] = str(v)

            if k in existing and existing[k] != sanitized.get(k):
                before_state[k] = existing[k]

        if image_file and getattr(image_file, "filename", None):
            image_url = save_upload_image(image_file, subfolder="products")
            sanitized["image_url"] = image_url
            if existing.get("image_url") != image_url:
                before_state["image_url"] = existing.get("image_url")

        if not sanitized:
            return True

        product_repo.update(pid, sanitized)

        # Audit log perubahan produk
        if actor_id and before_state:
            after_state = {k: sanitized[k] for k in before_state}
            audit_repo.log(
                actor_id=actor_id,
                action="product.update",
                entity_type="master_product",
                entity_id=pid,
                before=before_state,
                after=after_state,
            )

        return True

    def deactivate_product(self, product_id_input: any, actor_id: ObjectId | None = None) -> bool:
        """Admin: soft delete produk (is_active=false) (Bab 1.3 D4 & TC-PR-05)."""
        pid = validate_object_id(product_id_input, field_name="ID Produk")
        existing = product_repo.find_by_id(pid)
        if not existing:
            abort(404, description="Produk tidak ditemukan")

        product_repo.soft_delete(pid)

        if actor_id:
            audit_repo.log(
                actor_id=actor_id,
                action="product.deactivate",
                entity_type="master_product",
                entity_id=pid,
                before={"is_active": existing.get("is_active", True)},
                after={"is_active": False},
            )

        return True

    def create_category(self, name: str, slug: str, description: str | None = None, actor_id: ObjectId | None = None) -> ObjectId:
        valid_name = validate_string(name, min_len=2, max_len=60, field_name="Nama kategori")
        valid_slug = validate_string(slug, min_len=2, max_len=60, field_name="Slug").lower()
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", valid_slug):
            raise ValidationError("Slug kategori hanya boleh huruf kecil, angka, dan tanda hubung (-)", field="slug")

        if category_repo.find_by_slug(valid_slug):
            raise ConflictError(f"Slug kategori '{valid_slug}' sudah terdaftar.")

        cid = category_repo.insert(name=valid_name, slug=valid_slug, description=description, is_active=True)

        if actor_id:
            audit_repo.log(
                actor_id=actor_id,
                action="category.create",
                entity_type="categories",
                entity_id=cid,
                after={"name": valid_name, "slug": valid_slug},
            )

        return cid

    def deactivate_category(self, cat_id_input: any, actor_id: ObjectId | None = None) -> bool:
        """Nonaktifkan kategori. Ditolak bila masih memiliki produk aktif (Bab 12.2 & 14.5)."""
        cid = validate_object_id(cat_id_input, field_name="ID Kategori")
        existing = category_repo.find_by_id(cid)
        if not existing:
            abort(404, description="Kategori tidak ditemukan")

        active_prods_count = product_repo.count({"category_id": cid, "is_active": True})
        if active_prods_count > 0:
            raise ConflictError("Kategori tidak dapat dinonaktifkan karena masih memiliki produk aktif.")

        category_repo.update(cid, {"is_active": False})

        if actor_id:
            audit_repo.log(
                actor_id=actor_id,
                action="category.deactivate",
                entity_type="categories",
                entity_id=cid,
                before={"is_active": existing.get("is_active", True)},
                after={"is_active": False},
            )
        return True


catalog_service = CatalogService()

