"""Route blueprint untuk pengelolaan promosi dan voucher oleh admin (Bab 14.6)."""
from datetime import datetime, timezone
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from ...utils.decorators import login_required, admin_required
from ...repositories import promotion_repo, audit_repo
from ...models.enums import DiscountType
from ...utils.validators import validate_string, validate_enum, validate_object_id, ValidationError
from ...services.auth_service import ConflictError

admin_promotions_bp = Blueprint("admin_promotions", __name__, url_prefix="/admin/promotions")


@admin_promotions_bp.route("", methods=["GET"])
@login_required
@admin_required
def list_promotions():
    """Daftar voucher promosi (Bab 14.6)."""
    page = request.args.get("page", 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page

    promos = promotion_repo.find_all(skip=skip, limit=per_page)
    total = len(promos)

    return render_template(
        "admin/promotions.html",
        active="promotions",
        promotions=promos,
        page=page,
        total=total,
    )


@admin_promotions_bp.route("", methods=["POST"])
@login_required
@admin_required
def create_promotion():
    """Buat voucher baru (Bab 14.6 & TC-VC-01)."""
    admin_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form

    try:
        code = validate_string(data.get("code"), min_len=4, max_len=20, field_name="Kode voucher").upper()
        existing = promotion_repo.find_by_code(code)
        if existing:
            raise ConflictError(f"Kode voucher '{code}' sudah digunakan.", code=409)

        discount_type = validate_enum(data.get("discount_type"), DiscountType.ALL, field_name="Tipe diskon")
        try:
            val = int(data.get("value"))
            if val <= 0:
                raise ValidationError("Nilai diskon harus lebih dari 0", field="value", code=422)
        except (ValueError, TypeError):
            raise ValidationError("Nilai diskon harus berupa angka", field="value", code=422)

        min_order = int(data.get("min_order", 0))
        max_discount = int(data.get("max_discount")) if data.get("max_discount") else None
        quota = int(data.get("quota", 100))

        now = datetime.now(timezone.utc)
        starts_at_str = data.get("starts_at")
        ends_at_str = data.get("ends_at")

        starts_at = datetime.strptime(starts_at_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) if starts_at_str else now
        ends_at = datetime.strptime(ends_at_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc) if ends_at_str else now.replace(year=now.year + 1)

        promo_doc = {
            "code": code,
            "discount_type": discount_type,
            "value": val,
            "min_order": min_order,
            "max_discount": max_discount,
            "quota": quota,
            "used_count": 0,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "is_active": True,
        }

        promo_id = promotion_repo.insert(promo_doc)

        audit_repo.log(
            actor_id=admin_id,
            action="promotion.create",
            entity_type="promotions",
            entity_id=promo_id,
            after={"code": code, "value": val, "quota": quota},
        )

        if request.is_json:
            return jsonify({"ok": True, "data": {"_id": str(promo_id), "code": code}}), 201

        flash(f"Voucher '{code}' berhasil dibuat!", "success")
        return redirect(url_for("admin_promotions.list_promotions")), 302

    except ConflictError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "conflict", "message": e.message}}), 409
        flash(e.message, "error")
        promos = promotion_repo.find_all(limit=20)
        return render_template("admin/promotions.html", active="promotions", promotions=promos, page=1, total=len(promos)), 409
    except ValidationError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422
        flash(e.message, "error")
        promos = promotion_repo.find_all(limit=20)
        return render_template("admin/promotions.html", active="promotions", promotions=promos, page=1, total=len(promos)), 422


@admin_promotions_bp.route("/<promo_id>", methods=["PATCH", "POST"])
@login_required
@admin_required
def update_promotion(promo_id):
    """Ubah status / kuota voucher (used_count tidak dapat diubah manual) (Bab 14.6)."""
    admin_id = ObjectId(session["user_id"])
    pid = validate_object_id(promo_id, field_name="ID Promosi")
    promo = promotion_repo.find_by_id(pid)
    if not promo:
        raise ValidationError("Voucher tidak ditemukan", code=404)

    data = request.get_json(silent=True) or request.form
    updates = {}

    try:
        if "quota" in data:
            updates["quota"] = int(data["quota"])
        if "is_active" in data:
            updates["is_active"] = str(data["is_active"]).lower() in ["true", "1", "t"]

        if updates:
            promotion_repo.update(pid, updates)
            audit_repo.log(
                actor_id=admin_id,
                action="promotion.update",
                entity_type="promotions",
                entity_id=pid,
                before={"is_active": promo.get("is_active"), "quota": promo.get("quota")},
                after=updates,
            )

        if request.is_json:
            return jsonify({"ok": True, "data": {"_id": str(pid)}}), 200

        flash("Voucher berhasil diperbarui.", "success")
        return redirect(url_for("admin_promotions.list_promotions")), 302
    except ValidationError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422
        flash(e.message, "error")
        promos = promotion_repo.find_all(limit=20)
        return render_template("admin/promotions.html", active="promotions", promotions=promos, page=1, total=len(promos)), 422


@admin_promotions_bp.route("/<promo_id>", methods=["DELETE"])
@login_required
@admin_required
def deactivate_promotion(promo_id):
    """Nonaktifkan voucher (Bab 14.6)."""
    admin_id = ObjectId(session["user_id"])
    pid = validate_object_id(promo_id, field_name="ID Promosi")
    promo = promotion_repo.find_by_id(pid)
    if not promo:
        raise ValidationError("Voucher tidak ditemukan", code=404)

    promotion_repo.update(pid, {"is_active": False})

    audit_repo.log(
        actor_id=admin_id,
        action="promotion.deactivate",
        entity_type="promotions",
        entity_id=pid,
        before={"is_active": promo.get("is_active")},
        after={"is_active": False},
    )

    return jsonify({"ok": True, "data": {"_id": str(pid), "is_active": False}}), 200

