"""Route blueprint untuk manajemen order dan verifikasi pembayaran admin (Bab 14.6)."""
from datetime import datetime, timezone
import re
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, abort
from ...utils.decorators import login_required, admin_required
from ...services.order_service import order_service
from ...repositories import order_repo, user_repo
from ...models.enums import OrderStatus, PaymentStatus
from ...utils.validators import validate_object_id, ValidationError
from ...services.auth_service import ConflictError

admin_orders_bp = Blueprint("admin_orders", __name__, url_prefix="/admin")


@admin_orders_bp.route("/orders", methods=["GET"])
@login_required
@admin_required
def list_orders():
    """Daftar order pelanggan untuk admin (Bab 14.6)."""
    status = request.args.get("status")
    payment_status = request.args.get("payment_status")
    q = request.args.get("q")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = {}
    if status and status in OrderStatus.ALL:
        query["order_status"] = status
    if payment_status and payment_status in PaymentStatus.ALL:
        query["payment_status"] = payment_status
    if q and q.strip():
        safe_q = re.escape(q.strip()[:60])
        query["$or"] = [
            {"order_number": {"$regex": safe_q, "$options": "i"}},
            {"contact.name": {"$regex": safe_q, "$options": "i"}},
            {"contact.phone": {"$regex": safe_q, "$options": "i"}},
        ]

    if from_date or to_date:
        date_q = {}
        if from_date:
            try:
                date_q["$gte"] = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if to_date:
            try:
                date_q["$lte"] = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            except ValueError:
                pass
        if date_q:
            query["created_at"] = date_q

    total = order_repo.count(query)
    skip = (page - 1) * per_page
    orders = order_repo.find_all(query, sort_list=[("created_at", -1)], skip=skip, limit=per_page)

    return render_template(
        "admin/orders.html",
        active="orders",
        orders=orders,
        status=status,
        payment_status=payment_status,
        q=q or "",
        from_date=from_date or "",
        to_date=to_date or "",
        page=page,
        total=total,
        total_pages=(total + per_page - 1) // per_page if total > 0 else 1,
    )


@admin_orders_bp.route("/orders/<order_id>", methods=["GET"])
@login_required
@admin_required
def order_detail(order_id):
    """Detail pesanan pelanggan untuk admin (Bab 14.6)."""
    oid = validate_object_id(order_id, field_name="ID Order")
    order = order_repo.find_by_id(oid)
    if not order:
        abort(404, description="Pesanan tidak ditemukan")

    user = user_repo.find_by_id(order["user_id"])

    return render_template(
        "admin/order_detail.html",
        active="orders",
        order=order,
        user=user,
    )


@admin_orders_bp.route("/orders/<order_id>/status", methods=["PATCH", "POST"])
@login_required
@admin_required
def update_order_status(order_id):
    """Pembaruan status order oleh admin (Bab 7.E, 14.6 & TC-OR-01..05, 11)."""
    admin_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form
    new_status = data.get("status")
    note = data.get("note")

    try:
        updated_order = order_service.transition_order_status(
            order_id=order_id,
            to_status=new_status,
            actor_id=admin_id,
            note=note,
        )

        if request.is_json:
            return jsonify({"ok": True, "data": {"_id": str(updated_order["_id"]), "order_status": updated_order["order_status"]}}), 200

        flash(f"Status pesanan berhasil diubah menjadi {new_status}.", "success")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id)), 302
    except (ConflictError, ValidationError) as e:
        status_code = getattr(e, "code", 409 if isinstance(e, ConflictError) else 422)
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "conflict" if isinstance(e, ConflictError) else "validation_error", "message": e.message}}), status_code
        flash(e.message, "error")
        oid = validate_object_id(order_id)
        order = order_repo.find_by_id(oid)
        return render_template("admin/order_detail.html", active="orders", order=order), status_code


@admin_orders_bp.route("/payments", methods=["GET"])
@login_required
@admin_required
def list_payments():
    """Antrean verifikasi pembayaran untuk admin (Bab 14.6 & TC-OR-08)."""
    payment_status = request.args.get("payment_status", PaymentStatus.AWAITING_VERIFICATION)
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = {}
    if payment_status:
        query["payment_status"] = payment_status

    total = order_repo.count(query)
    skip = (page - 1) * per_page
    orders = order_repo.find_all(query, sort_list=[("created_at", -1)], skip=skip, limit=per_page)

    return render_template(
        "admin/payments.html",
        active="payments",
        orders=orders,
        payment_status=payment_status,
        page=page,
        total=total,
        total_pages=(total + per_page - 1) // per_page if total > 0 else 1,
    )


@admin_orders_bp.route("/orders/<order_id>/payment", methods=["PATCH", "POST"])
@login_required
@admin_required
def update_payment(order_id):
    """Verifikasi / penolakan bukti transfer atau tandai lunas COD (Bab 7.E, 14.6 & TC-OR-08)."""
    admin_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form
    action = data.get("action")
    note = data.get("note")

    try:
        updated_order = order_service.verify_payment(
            order_id=order_id,
            actor_id=admin_id,
            action=action,
            note=note,
        )

        if request.is_json:
            return jsonify({"ok": True, "data": {"_id": str(updated_order["_id"]), "payment_status": updated_order["payment_status"]}}), 200

        flash("Status pembayaran berhasil diperbarui.", "success")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id)), 302
    except (ConflictError, ValidationError) as e:
        status_code = getattr(e, "code", 409 if isinstance(e, ConflictError) else 422)
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "conflict" if isinstance(e, ConflictError) else "validation_error", "message": e.message}}), status_code
        flash(e.message, "error")
        oid = validate_object_id(order_id)
        order = order_repo.find_by_id(oid)
        return render_template("admin/order_detail.html", active="orders", order=order), status_code

