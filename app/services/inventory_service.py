"""Inventory service: Logika mutasi stok, opname, dan deteksi low-stock (Bab 7.F, 11.4, 14.5)."""
from bson import ObjectId
from ..extensions import get_client
from ..repositories import product_repo, stock_repo, audit_repo, notification_repo
from ..models.enums import StockMovementType, StockReferenceType, NotificationType
from ..utils.validators import validate_object_id, validate_string, ValidationError
from .auth_service import ConflictError


class InventoryService:
    def adjust_stock(
        self,
        product_id: ObjectId | str,
        movement_type: str,
        actor_id: ObjectId,
        quantity: int | None = None,
        new_stock: int | None = None,
        note: str | None = None,
    ) -> dict:
        """Penyesuaian stok (addition atau correction) dengan invarian after = before + qty (Bab 7.F)."""
        pid = validate_object_id(product_id, field_name="ID Produk")
        prod = product_repo.find_by_id(pid)
        if not prod:
            raise ValidationError("Produk tidak ditemukan", code=404)

        before_stock = prod.get("stock", 0)

        if movement_type == StockMovementType.ADDITION:
            # Penambahan stok (restock): quantity > 0
            if quantity is None:
                raise ValidationError("Kuantitas penambahan stok wajib diisi", field="quantity", code=422)
            try:
                qty_int = int(quantity)
            except (ValueError, TypeError):
                raise ValidationError("Kuantitas harus berupa angka", field="quantity", code=422)

            if qty_int <= 0:
                raise ValidationError("Kuantitas penambahan harus lebih besar dari 0", field="quantity", code=422)

            after_stock = before_stock + qty_int
            clean_note = validate_string(note, max_len=200, field_name="Catatan") if note else None

            # Update stok di master_product
            product_repo.inc_stock(pid, qty_int)

            # Record append-only stock_movements
            movement_id = stock_repo.insert(
                product_id=pid,
                movement_type=StockMovementType.ADDITION,
                quantity=qty_int,
                before_stock=before_stock,
                after_stock=after_stock,
                reference_type=StockReferenceType.MANUAL,
                reference_id=None,
                actor_id=actor_id,
                note=clean_note,
            )

            # Audit log
            audit_repo.log(
                actor_id=actor_id,
                action="inventory.adjust",
                entity_type="stock_movements",
                entity_id=movement_id,
                before={"stock": before_stock},
                after={"stock": after_stock, "type": StockMovementType.ADDITION, "quantity": qty_int},
            )

            return {
                "product_id": str(pid),
                "before_stock": before_stock,
                "after_stock": after_stock,
                "quantity": qty_int,
                "movement_type": StockMovementType.ADDITION,
            }

        elif movement_type == StockMovementType.CORRECTION:
            # Koreksi stok opname: catatan wajib diisi (Bab 7.F & TC-IN-02)
            if not note or not note.strip():
                raise ValidationError("Catatan wajib diisi untuk koreksi stok (stock opname)", field="note", code=422)
            clean_note = validate_string(note, min_len=3, max_len=200, field_name="Catatan koreksi")

            # Hitung after_stock dan diff
            if new_stock is not None:
                try:
                    target_stock = int(new_stock)
                except (ValueError, TypeError):
                    raise ValidationError("Stok baru harus berupa bilangan bulat", field="new_stock", code=422)
                if target_stock < 0:
                    raise ValidationError("Stok tidak boleh negatif", field="new_stock", code=422)
                after_stock = target_stock
                diff = after_stock - before_stock
            elif quantity is not None:
                try:
                    diff = int(quantity)
                except (ValueError, TypeError):
                    raise ValidationError("Selisih kuantitas harus berupa bilangan bulat", field="quantity", code=422)
                after_stock = before_stock + diff
                if after_stock < 0:
                    raise ValidationError("Stok hasil koreksi tidak boleh negatif", field="quantity", code=422)
            else:
                raise ValidationError("Nilai stok baru atau selisih kuantitas wajib diisi", code=422)

            # Invarian check: after = before + diff dan after >= 0
            if after_stock != before_stock + diff or after_stock < 0:
                raise ValidationError("Invarian pergerakan stok tidak valid", code=422)

            # Update master_product
            product_repo.set_stock(pid, after_stock)

            # Record stock_movements
            movement_id = stock_repo.insert(
                product_id=pid,
                movement_type=StockMovementType.CORRECTION,
                quantity=diff,
                before_stock=before_stock,
                after_stock=after_stock,
                reference_type=StockReferenceType.STOCKTAKE,
                reference_id=None,
                actor_id=actor_id,
                note=clean_note,
            )

            # Audit log
            audit_repo.log(
                actor_id=actor_id,
                action="inventory.adjust",
                entity_type="stock_movements",
                entity_id=movement_id,
                before={"stock": before_stock},
                after={"stock": after_stock, "type": StockMovementType.CORRECTION, "diff": diff, "note": clean_note},
            )

            return {
                "product_id": str(pid),
                "before_stock": before_stock,
                "after_stock": after_stock,
                "quantity": diff,
                "movement_type": StockMovementType.CORRECTION,
            }
        else:
            raise ValidationError(f"Tipe penyesuaian stok '{movement_type}' tidak valid", field="type", code=422)

    def get_inventory_status(
        self,
        low_stock_only: bool = False,
        q: str | None = None,
        page: int = 1,
        per_page: int = 20,
        status_filter: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        **kwargs,
    ):
        """Mendapatkan daftar stok inventori dengan filter low-stock (Bab 14.5)."""
        import re

        if search and not q:
            q = search
        if limit and limit > 0:
            per_page = limit
        if status_filter == "low_stock" or status_filter in ["1", "true", "True"]:
            low_stock_only = True
        query = {"is_active": True}
        if low_stock_only:
            query["$expr"] = {"$lte": ["$stock", "$min_stock"]}
        if q and q.strip():
            safe_q = re.escape(q.strip()[:60])
            query["$or"] = [
                {"name": {"$regex": safe_q, "$options": "i"}},
                {"sku": safe_q.upper()},
            ]

        total = product_repo.count(query)
        skip = (page - 1) * per_page
        sort_list = [("stock", 1), ("name", 1)]
        products = product_repo.find_all(query, sort_list=sort_list, skip=skip, limit=per_page)

        return {
            "products": products,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
        }

    def get_movements_history(
        self,
        product_id: str | None = None,
        movement_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ):
        """Riwayat mutasi stok append-only (Bab 14.5)."""
        from ..repositories import user_repo

        query = {}
        if product_id and product_id.strip():
            pid = validate_object_id(product_id)
            query["product_id"] = pid
        if movement_type and movement_type.strip():
            query["movement_type"] = movement_type.strip()

        total = stock_repo.count(query)
        skip = (page - 1) * per_page
        movements = stock_repo.find_all(query, skip=skip, limit=per_page)

        # Populasi data produk & aktor untuk tampilan
        enriched = []
        for m in movements:
            prod = product_repo.find_by_id(m.get("product_id"))
            actor = user_repo.find_by_id(m.get("actor_id"))
            enriched.append({
                **m,
                "product_name": prod.get("name") if prod else "-",
                "product_sku": prod.get("sku") if prod else "-",
                "actor_name": actor.get("name") if actor else "-",
                "actor_email": actor.get("email") if actor else "-",
            })

        return {
            "movements": enriched,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
        }


inventory_service = InventoryService()

