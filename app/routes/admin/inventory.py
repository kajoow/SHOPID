"""Route blueprint untuk inventori dan mutasi stok oleh admin (Bab 14.5)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from ...utils.decorators import login_required, admin_required
from ...services.inventory_service import inventory_service
from ...utils.validators import ValidationError
from ...services.auth_service import ConflictError

admin_inventory_bp = Blueprint("admin_inventory", __name__, url_prefix="/admin/inventory")


@admin_inventory_bp.route("", methods=["GET"])
@login_required
@admin_required
def inventory_status():
    """Daftar stok produk dan deteksi stok rendah (Bab 7.F, 14.5 & TC-IN-04)."""
    low_stock = request.args.get("low_stock") in ["1", "true", "True"]
    q = request.args.get("q")
    page = request.args.get("page", 1, type=int)

    result = inventory_service.get_inventory_status(low_stock_only=low_stock, q=q, page=page, per_page=20)

    return render_template(
        "admin/inventory.html",
        active="inventory",
        products=result["products"],
        low_stock=low_stock,
        q=q or "",
        page=page,
        total=result["total"],
        total_pages=result["total_pages"],
    )


@admin_inventory_bp.route("/<product_id>/adjust", methods=["POST"])
@login_required
@admin_required
def adjust_stock(product_id):
    """Penyesuaian stok (addition / correction) (Bab 7.F, 14.5 & TC-IN-01..03, 05)."""
    admin_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form

    movement_type = data.get("type") or data.get("movement_type")
    quantity = data.get("quantity")
    new_stock = data.get("new_stock")
    note = data.get("note")

    try:
        res = inventory_service.adjust_stock(
            product_id=product_id,
            movement_type=movement_type,
            actor_id=admin_id,
            quantity=quantity,
            new_stock=new_stock,
            note=note,
        )

        if request.is_json:
            return jsonify({"ok": True, "data": res}), 200

        flash("Stok berhasil diperbarui.", "success")
        return redirect(url_for("admin_inventory.inventory_status")), 302
    except (ValidationError, ConflictError) as e:
        if request.is_json:
            status_code = 422 if isinstance(e, ValidationError) else 409
            code_name = "validation_error" if isinstance(e, ValidationError) else "conflict"
            return jsonify({"ok": False, "error": {"code": code_name, "message": e.message, "field": getattr(e, "field", None)}}), status_code
        flash(e.message, "error")
        low_stock = request.args.get("low_stock") in ["1", "true", "True"]
        q = request.args.get("q")
        page = request.args.get("page", 1, type=int)
        result = inventory_service.get_inventory_status(low_stock_only=low_stock, q=q, page=page, per_page=20)
        return render_template(
            "admin/inventory.html",
            active="inventory",
            products=result["products"],
            low_stock=low_stock,
            q=q or "",
            page=page,
            total=result["total"],
            total_pages=result["total_pages"],
        ), 422


@admin_inventory_bp.route("/movements", methods=["GET"])
@login_required
@admin_required
def inventory_movements():
    """Riwayat mutasi stok append-only (Bab 7.F, 14.5 & TC-IN-05)."""
    product_id = request.args.get("product_id")
    movement_type = request.args.get("type")
    page = request.args.get("page", 1, type=int)

    result = inventory_service.get_movements_history(
        product_id=product_id,
        movement_type=movement_type,
        page=page,
        per_page=20,
    )

    return render_template(
        "admin/inventory_movements.html",
        active="inventory",
        movements=result["movements"],
        product_id=product_id or "",
        movement_type=movement_type or "",
        page=page,
        total=result["total"],
        total_pages=result["total_pages"],
    )

