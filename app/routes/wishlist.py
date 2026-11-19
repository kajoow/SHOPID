"""Route blueprint untuk modul Wishlist pelanggan (Bab 14.4 & TC-WL-01)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, session
from ..utils.decorators import login_required, customer_only
from ..repositories import wishlist_repo, product_repo
from ..utils.validators import validate_object_id, ValidationError

wishlist_bp = Blueprint("wishlist", __name__, url_prefix="/wishlist")


@wishlist_bp.route("", methods=["GET"])
@login_required
@customer_only
def view_wishlist():
    """Halaman daftar produk favorit (wishlist) pelanggan (Bab 14.4)."""
    user_id = ObjectId(session["user_id"])
    wishlist_doc = wishlist_repo.find_by_user_id(user_id)
    product_ids = wishlist_doc.get("product_ids", []) if wishlist_doc else []

    products = []
    for pid in product_ids:
        p = product_repo.find_by_id(pid)
        if p and p.get("is_active", True):
            products.append(p)

    return render_template("user/wishlist.html", products=products)


@wishlist_bp.route("/items", methods=["POST"])
@login_required
@customer_only
def add_to_wishlist():
    """Menambahkan produk ke wishlist secara idempoten / set unik (Bab 14.4 & TC-WL-01)."""
    user_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form
    raw_pid = data.get("product_id")

    pid = validate_object_id(raw_pid, field_name="ID Produk")
    prod = product_repo.find_by_id(pid)
    if not prod or not prod.get("is_active", True):
        raise ValidationError("Produk tidak ditemukan atau tidak aktif", code=404)

    wishlist_repo.add_item(user_id, pid)

    return jsonify({"ok": True, "data": {"product_id": str(pid)}}), 201


@wishlist_bp.route("/items/<product_id>", methods=["DELETE"])
@login_required
@customer_only
def remove_from_wishlist(product_id):
    """Menghapus produk dari wishlist (Bab 14.4)."""
    user_id = ObjectId(session["user_id"])
    pid = validate_object_id(product_id, field_name="ID Produk")

    wishlist_repo.remove_item(user_id, pid)

    return jsonify({"ok": True, "data": {"product_id": str(pid)}}), 200

