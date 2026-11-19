"""Cart service: Logika bisnis keranjang belanja persisten (Bab 7.C, 14.3)."""
from bson import ObjectId
from flask import abort

from ..repositories import cart_repo, product_repo
from ..utils.validators import validate_object_id, validate_int, ValidationError
from .auth_service import ConflictError


class CartService:
    def get_cart_view(self, user_id: ObjectId) -> dict:
        """Membaca keranjang persisten user dengan harga dan ketersediaan stok terkini dari master_product (Bab 7.C)."""
        cart = cart_repo.ensure_cart(user_id)
        raw_items = cart.get("items", [])

        enriched_items = []
        subtotal = 0
        has_unavailable = False

        for item in raw_items:
            prod = product_repo.find_by_id(item["product_id"])
            if not prod:
                continue

            qty = item["quantity"]
            is_active = prod.get("is_active", False)
            available_stock = prod.get("stock", 0)
            is_available = is_active and (available_stock >= qty)

            if not is_available:
                has_unavailable = True

            price = prod.get("price", 0)
            line_total = price * qty
            if is_available:
                subtotal += line_total

            enriched_items.append({
                "product": prod,
                "quantity": qty,
                "line_total": line_total,
                "is_available": is_available,
                "available_stock": available_stock,
            })

        return {
            "items": enriched_items,
            "subtotal": subtotal,
            "has_unavailable": has_unavailable,
            "raw_items_count": len(raw_items),
        }

    def add_to_cart(self, user_id: ObjectId, product_id_input: any, quantity_input: any = 1):
        """Menambah produk ke keranjang. Jika sudah ada, kuantitas digabung (Bab 7.C)."""
        pid = validate_object_id(product_id_input, field_name="ID Produk")
        qty = validate_int(quantity_input, min_val=1, max_val=99, field_name="Kuantitas")

        prod = product_repo.find_by_id(pid)
        if not prod or not prod.get("is_active", True):
            abort(404, description="Produk tidak ditemukan atau tidak aktif")

        current_stock = prod.get("stock", 0)
        if current_stock <= 0:
            raise ConflictError("Stok produk sedang habis")

        # Cek kuantitas saat ini di keranjang user
        cart = cart_repo.ensure_cart(user_id)
        current_in_cart = 0
        for it in cart.get("items", []):
            if it["product_id"] == pid:
                current_in_cart = it["quantity"]
                break

        total_qty = current_in_cart + qty
        if total_qty > 99:
            raise ValidationError("Kuantitas maksimum dalam keranjang adalah 99 unit", field="quantity", code=422)

        if total_qty > current_stock:
            raise ConflictError(f"Stok tidak mencukupi. Tersedia: {current_stock}, di keranjang: {current_in_cart}")

        cart_repo.add_or_update_item(user_id, pid, qty)
        return True

    def update_quantity(self, user_id: ObjectId, product_id_input: any, quantity_input: any):
        """Mengubah kuantitas item (1-99). Kuantitas 0 dilarang, harus gunakan DELETE (Bab 7.C)."""
        pid = validate_object_id(product_id_input, field_name="ID Produk")
        qty = validate_int(quantity_input, min_val=1, max_val=99, field_name="Kuantitas")

        prod = product_repo.find_by_id(pid)
        if not prod or not prod.get("is_active", True):
            abort(404, description="Produk tidak ditemukan atau tidak aktif")

        current_stock = prod.get("stock", 0)
        if qty > current_stock:
            raise ConflictError(f"Kuantitas ({qty}) melebihi stok yang tersedia ({current_stock}).")

        cart = cart_repo.find_by_user_id(user_id)
        if not cart:
            abort(404, description="Keranjang tidak ditemukan")

        found = any(it["product_id"] == pid for it in cart.get("items", []))
        if not found:
            abort(404, description="Item tidak ditemukan di keranjang")

        cart_repo.set_item_quantity(user_id, pid, qty)
        return True

    def remove_item(self, user_id: ObjectId, product_id_input: any):
        pid = validate_object_id(product_id_input, field_name="ID Produk")
        cart_repo.remove_item(user_id, pid)
        return True


cart_service = CartService()

