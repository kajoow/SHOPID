"""Route blueprint untuk manajemen kategori oleh admin (Bab 14.5)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from ...utils.decorators import login_required, admin_required
from ...services.catalog_service import catalog_service
from ...repositories import category_repo
from ...services.auth_service import ConflictError
from ...utils.validators import ValidationError

admin_categories_bp = Blueprint("admin_categories", __name__, url_prefix="/admin/categories")


@admin_categories_bp.route("", methods=["GET"])
@login_required
@admin_required
def list_categories():
    """Daftar kategori di konsol admin (Bab 14.5)."""
    categories = category_repo.find_all()
    return render_template(
        "admin/categories.html",
        active="categories",
        categories=categories,
    )


@admin_categories_bp.route("", methods=["POST"])
@login_required
@admin_required
def create_category():
    """Buat kategori baru (Bab 14.5)."""
    name = request.form.get("name")
    slug = request.form.get("slug")
    description = request.form.get("description")
    actor_id = ObjectId(session["user_id"])

    try:
        cid = catalog_service.create_category(
            name=name,
            slug=slug,
            description=description,
            actor_id=actor_id,
        )
        if request.is_json:
            return jsonify({"ok": True, "data": {"_id": str(cid)}}), 201

        flash(f"Kategori '{name}' berhasil dibuat.", "success")
        return redirect(url_for("admin_categories.list_categories")), 302
    except ConflictError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "conflict", "message": e.message}}), 409
        flash(e.message, "error")
        categories = category_repo.find_all()
        return render_template("admin/categories.html", active="categories", categories=categories), 409
    except ValidationError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422
        flash(e.message, "error")
        categories = category_repo.find_all()
        return render_template("admin/categories.html", active="categories", categories=categories), 422


@admin_categories_bp.route("/<category_id>", methods=["PATCH"])
@login_required
@admin_required
def update_category(category_id):
    """Ubah kategori (Bab 14.5)."""
    data = request.get_json(silent=True) or request.form.to_dict()
    cid = ObjectId(category_id)
    updates = {}
    if "name" in data:
        updates["name"] = data["name"]
    if "description" in data:
        updates["description"] = data["description"]
    if "is_active" in data:
        updates["is_active"] = bool(data["is_active"])

    category_repo.update(cid, updates)
    return jsonify({"ok": True, "data": {"message": "Kategori berhasil diperbarui"}}), 200


@admin_categories_bp.route("/<category_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_category(category_id):
    """Nonaktifkan kategori (ditolak bila masih memiliki produk aktif) (Bab 12.2, 14.5)."""
    actor_id = ObjectId(session["user_id"])
    try:
        catalog_service.deactivate_category(category_id, actor_id=actor_id)
        return jsonify({"ok": True, "data": {"message": "Kategori berhasil dinonaktifkan"}}), 200
    except ConflictError as e:
        return jsonify({"ok": False, "error": {"code": "conflict", "message": e.message}}), 409

