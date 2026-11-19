"""Route blueprint untuk manajemen produk oleh admin (Bab 14.5)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, abort
from ...utils.decorators import login_required, admin_required
from ...services.catalog_service import catalog_service
from ...repositories import product_repo, category_repo
from ...services.auth_service import ConflictError
from ...utils.validators import ValidationError

admin_products_bp = Blueprint("admin_products", __name__, url_prefix="/admin/products")


@admin_products_bp.route("", methods=["GET"])
@login_required
@admin_required
def list_products():
    """Daftar produk di konsol admin (Bab 14.5)."""
    q = request.args.get("q")
    category = request.args.get("category")
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)

    query = {}
    if status == "active":
        query["is_active"] = True
    elif status == "inactive":
        query["is_active"] = False

    if category:
        cat = category_repo.find_by_slug(category)
        if cat:
            query["category_id"] = cat["_id"]

    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"sku": q.upper()},
        ]

    per_page = 20
    skip = (max(1, page) - 1) * per_page
    products = product_repo.find_all(query, [("created_at", -1)], skip=skip, limit=per_page)
    categories = category_repo.find_all()

    # Map nama kategori ke produk untuk kemudahan tampilan
    cat_dict = {c["_id"]: c["name"] for c in categories}
    for p in products:
        p["category_name"] = cat_dict.get(p.get("category_id"), "-")

    return render_template(
        "admin/products.html",
        active="products",
        products=products,
        categories=categories,
        page=page,
    )


@admin_products_bp.route("", methods=["POST"])
@login_required
@admin_required
def create_product():
    """Buat produk baru beserta stok awal initial (Bab 14.5 & TC-PR-01)."""
    sku = request.form.get("sku")
    name = request.form.get("name")
    category_id = request.form.get("category_id")
    price = request.form.get("price")
    stock = request.form.get("stock", 0)
    min_stock = request.form.get("min_stock", 5)
    description = request.form.get("description")
    image_file = request.files.get("image")

    actor_id = ObjectId(session["user_id"])

    try:
        pid = catalog_service.create_product(
            sku=sku,
            name=name,
            category_id_input=category_id,
            price_input=price,
            stock_input=stock,
            min_stock_input=min_stock,
            description=description,
            image_file=image_file,
            actor_id=actor_id,
        )

        if request.is_json:
            return jsonify({"ok": True, "data": {"_id": str(pid)}}), 201

        flash(f"Produk '{name}' berhasil ditambahkan.", "success")
        return redirect(url_for("admin_products.list_products")), 302

    except ConflictError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "conflict", "message": e.message}}), 409
        flash(e.message, "error")
        categories = category_repo.find_all()
        products = product_repo.find_all({}, [("created_at", -1)], limit=20)
        cat_map = {str(c["_id"]): c["name"] for c in categories}
        for p in products:
            p["category_name"] = cat_map.get(str(p.get("category_id")), "-")
        return render_template("admin/products.html", active="products", products=products, categories=categories, total=len(products), page=1, total_pages=1), 409
    except ValidationError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422
        flash(e.message, "error")
        categories = category_repo.find_all()
        products = product_repo.find_all({}, [("created_at", -1)], limit=20)
        cat_map = {str(c["_id"]): c["name"] for c in categories}
        for p in products:
            p["category_name"] = cat_map.get(str(p.get("category_id")), "-")
        return render_template("admin/products.html", active="products", products=products, categories=categories, total=len(products), page=1, total_pages=1), 422


@admin_products_bp.route("/<product_id>", methods=["GET"])
@login_required
@admin_required
def get_product(product_id):
    """Mendapatkan data produk (JSON) untuk form edit (Bab 14.5)."""
    prod = product_repo.find_by_id(product_id)
    if not prod:
        abort(404, description="Produk tidak ditemukan")
    prod["_id"] = str(prod["_id"])
    if "category_id" in prod and prod["category_id"]:
        prod["category_id"] = str(prod["category_id"])
    return jsonify({"ok": True, "data": prod}), 200


@admin_products_bp.route("/<product_id>", methods=["PATCH", "POST"])
@login_required
@admin_required
def update_product(product_id):
    """Ubah data produk (stok dilarang, gunakan modul inventori) (Bab 14.5 & TC-PR-06)."""
    actor_id = ObjectId(session["user_id"])
    image_file = request.files.get("image") if request.files else None

    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    try:
        catalog_service.update_product(
            product_id_input=product_id,
            updates_data=data,
            image_file=image_file,
            actor_id=actor_id,
        )
        if request.is_json or request.method == "PATCH" or "application/json" in request.headers.get("Accept", ""):
            return jsonify({"ok": True, "data": {"message": "Produk berhasil diperbarui"}}), 200

        flash("Produk berhasil diperbarui.", "success")
        return redirect(url_for("admin_products.list_products")), 302

    except ValidationError as e:
        if request.is_json or request.method == "PATCH" or "application/json" in request.headers.get("Accept", ""):
            return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422

        flash(e.message, "error")
        categories = category_repo.find_all()
        products = product_repo.find_all({}, [("created_at", -1)], limit=20)
        cat_map = {str(c["_id"]): c["name"] for c in categories}
        for p in products:
            p["category_name"] = cat_map.get(str(p.get("category_id")), "-")
        return render_template(
            "admin/products.html",
            active="products",
            products=products,
            categories=categories,
            total=len(products),
            page=1,
            total_pages=1,
        ), 422


@admin_products_bp.route("/<product_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_product(product_id):
    """Soft delete produk (is_active=false) (Bab 1.3 D4 & TC-PR-05)."""
    actor_id = ObjectId(session["user_id"])
    catalog_service.deactivate_product(product_id, actor_id=actor_id)
    return jsonify({"ok": True, "data": {"message": "Produk berhasil dinonaktifkan"}}), 200

