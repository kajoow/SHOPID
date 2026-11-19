"""Route blueprint untuk keranjang belanja (Bab 14.3)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, session
from ..utils.decorators import login_required, customer_only
from ..services.cart_service import cart_service
from ..services.auth_service import ConflictError
from ..utils.validators import ValidationError

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


@cart_bp.route("", methods=["GET"])
@login_required
@customer_only
def view_cart():
    """Halaman melihat keranjang belanja (Bab 14.3)."""
    user_id = ObjectId(session["user_id"])
    cart_data = cart_service.get_cart_view(user_id)
    return render_template(
        "user/cart.html",
        items=cart_data["items"],
        subtotal=cart_data["subtotal"],
        has_unavailable=cart_data["has_unavailable"],
    )


@cart_bp.route("/items", methods=["POST"])
@login_required
@customer_only
def add_item():
    """Tambah produk ke keranjang belanja (Bab 14.3 & TC-CT-01)."""
    user_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form

    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)

    try:
        cart_service.add_to_cart(user_id, product_id, quantity)
        cart_data = cart_service.get_cart_view(user_id)
        return jsonify({
            "ok": True,
            "data": {
                "message": "Item berhasil ditambahkan ke keranjang",
                "subtotal": cart_data["subtotal"],
                "cart_count": len(cart_data["items"]),
            }
        }), 201
    except ConflictError as e:
        return jsonify({"ok": False, "error": {"code": "stock_conflict", "message": e.message}}), 409
    except ValidationError as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422


@cart_bp.route("/items/<product_id>", methods=["PATCH"])
@login_required
@customer_only
def update_item_quantity(product_id):
    """Ubah kuantitas item keranjang (Bab 14.3 & TC-CT-05)."""
    user_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form
    quantity = data.get("quantity")

    try:
        cart_service.update_quantity(user_id, product_id, quantity)
        cart_data = cart_service.get_cart_view(user_id)
        return jsonify({
            "ok": True,
            "data": {
                "message": "Kuantitas berhasil diubah",
                "subtotal": cart_data["subtotal"],
            }
        }), 200
    except ConflictError as e:
        return jsonify({"ok": False, "error": {"code": "stock_conflict", "message": e.message}}), 409
    except ValidationError as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422


@cart_bp.route("/items/<product_id>", methods=["DELETE"])
@login_required
@customer_only
def remove_item(product_id):
    """Hapus item dari keranjang (Bab 14.3 & TC-CT-05)."""
    user_id = ObjectId(session["user_id"])
    cart_service.remove_item(user_id, product_id)
    return jsonify({"ok": True, "data": {"message": "Item berhasil dihapus"}}), 200
