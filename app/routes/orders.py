"""Route blueprint untuk checkout dan order pelanggan (Bab 14.3)."""
import uuid
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app, abort
from ..utils.decorators import login_required, customer_only
from ..services.cart_service import cart_service
from ..services.order_service import order_service
from ..services.promotion_service import promotion_service
from ..services.auth_service import ConflictError
from ..utils.validators import ValidationError, validate_object_id
from ..repositories import order_repo

orders_bp = Blueprint("orders", __name__)


@orders_bp.route("/checkout", methods=["GET"])
@login_required
@customer_only
def checkout():
    """Halaman checkout pesanan: mengeluarkan idempotency_key baru (Bab 14.3)."""
    user_id = ObjectId(session["user_id"])
    cart_data = cart_service.get_cart_view(user_id)

    if not cart_data["items"] or cart_data["subtotal"] <= 0:
        flash("Keranjang belanja Anda masih kosong. Silakan pilih produk terlebih dahulu.", "info")
        return redirect(url_for("cart.view_cart")), 302

    idempotency_key = str(uuid.uuid4())
    delivery_fee = current_app.config.get("DELIVERY_FEE", 10000)

    return render_template(
        "user/checkout.html",
        items=cart_data["items"],
        subtotal=cart_data["subtotal"],
        delivery_fee=delivery_fee,
        idempotency_key=idempotency_key,
    )


@orders_bp.route("/checkout/voucher", methods=["POST"])
@login_required
@customer_only
def preview_voucher():
    """Pratinjau diskon voucher sebelum submit order (Bab 14.3)."""
    user_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form
    code = data.get("code")

    cart_data = cart_service.get_cart_view(user_id)
    subtotal = cart_data["subtotal"]

    try:
        discount, promo = promotion_service.validate_and_calculate_discount(code, subtotal)
        total = max(0, subtotal - discount)
        return jsonify({
            "ok": True,
            "data": {
                "discount": discount,
                "total": total,
                "code": promo["code"],
            }
        }), 200
    except ValidationError as e:
        return jsonify({"ok": False, "error": {"code": "invalid_voucher", "message": e.message}}), 422


@orders_bp.route("/orders", methods=["POST"])
@login_required
@customer_only
def create_order():
    """Membuat order baru dari keranjang belanja secara atomik (Bab 7.D, 14.3)."""
    user_id = ObjectId(session["user_id"])
    data = request.form if request.form else (request.get_json(silent=True) or {})

    contact_name = data.get("contact_name")
    contact_phone = data.get("contact_phone")
    fulfillment_method = data.get("fulfillment_method")
    payment_method = data.get("payment_method")
    idempotency_key = data.get("idempotency_key")
    shipping_address = data.get("shipping_address")
    voucher_code = data.get("voucher_code")

    try:
        order = order_service.create_order(
            user_id=user_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            fulfillment_method=fulfillment_method,
            payment_method=payment_method,
            idempotency_key=idempotency_key,
            shipping_address_str=shipping_address,
            voucher_code=voucher_code,
        )

        order_id = str(order["_id"])
        if request.is_json:
            return jsonify({"ok": True, "data": {"_id": order_id, "order_number": order["order_number"]}}), 201

        flash(f"Pesanan {order['order_number']} berhasil dibuat!", "success")
        return redirect(url_for("orders.order_confirmation", order_id=order_id)), 302

    except ConflictError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "stock_conflict", "message": e.message}}), 409
        flash(e.message, "error")
        cart_view = cart_service.get_cart_view(user_id)
        return render_template("user/cart.html", items=cart_view["items"], subtotal=cart_view["subtotal"]), 409
    except ValidationError as e:
        status_code = getattr(e, "code", 422)
        if request.is_json:
            err_code = "bad_request" if status_code == 400 else "validation_error"
            return jsonify({"ok": False, "error": {"code": err_code, "message": e.message, "field": e.field}}), status_code
        flash(e.message, "error")
        if status_code == 400:
            cart_view = cart_service.get_cart_view(user_id)
            return render_template("user/cart.html", items=cart_view["items"], subtotal=cart_view["subtotal"]), 400
        else:
            cart_data = cart_service.get_cart_view(user_id)
            idempotency_key = request.form.get("idempotency_key") or str(uuid.uuid4())
            delivery_fee = current_app.config.get("DELIVERY_FEE", 10000)
            return render_template(
                "user/checkout.html",
                items=cart_data["items"],
                subtotal=cart_data["subtotal"],
                delivery_fee=delivery_fee,
                idempotency_key=idempotency_key,
            ), status_code


@orders_bp.route("/orders/<order_id>/confirmation", methods=["GET"])
@login_required
@customer_only
def order_confirmation(order_id):
    """Halaman konfirmasi order (Bab 14.3 & TC-RB-04)."""
    user_id = ObjectId(session["user_id"])
    oid = validate_object_id(order_id, field_name="ID Order")
    order = order_repo.find_by_id(oid)

    # Pemeriksaan kepemilikan data: order milik user lain = 404 (Bab 16.4 & TC-RB-04)
    if not order or order.get("user_id") != user_id:
        abort(404, description="Pesanan tidak ditemukan")

    return render_template("user/order_confirmation.html", order=order)


@orders_bp.route("/orders/my", methods=["GET"])
@login_required
@customer_only
def my_orders():
    """Riwayat pesanan pelanggan (Bab 14.3)."""
    user_id = ObjectId(session["user_id"])
    orders = order_repo.find_all({"user_id": user_id}, sort_list=[("created_at", -1)])
    return render_template("user/orders.html", orders=orders)


@orders_bp.route("/orders/<order_id>", methods=["GET"])
@login_required
@customer_only
def order_detail(order_id):
    """Detail dan pelacakan status pesanan (Bab 14.3 & TC-RB-04)."""
    user_id = ObjectId(session["user_id"])
    oid = validate_object_id(order_id, field_name="ID Order")
    order = order_repo.find_by_id(oid)

    # Kepemilikan data: bukan milik user = 404
    if not order or order.get("user_id") != user_id:
        abort(404, description="Pesanan tidak ditemukan")

    return render_template("user/order_detail.html", order=order)


@orders_bp.route("/orders/<order_id>/cancel", methods=["POST"])
@login_required
@customer_only
def cancel_order(order_id):
    """Batalkan pesanan oleh pelanggan saat status pending (Bab 7.E, 14.3 & TC-OR-09..10)."""
    user_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form
    note = data.get("note", "Dibatalkan oleh pelanggan")

    order = order_service.cancel_order(order_id, actor_id=user_id, is_admin=False, note=note)

    if request.is_json:
        return jsonify({"ok": True, "data": {"_id": str(order["_id"]), "order_status": order["order_status"]}}), 200

    flash("Pesanan berhasil dibatalkan dan stok telah dipulihkan.", "info")
    return redirect(url_for("orders.order_detail", order_id=order_id)), 302


@orders_bp.route("/orders/<order_id>/payment-proof", methods=["POST"])
@login_required
@customer_only
def upload_payment_proof(order_id):
    """Unggah berkas bukti transfer oleh pelanggan (Bab 7.E, 14.3 & TC-OR-06..07)."""
    from flask import abort

    user_id = ObjectId(session["user_id"])
    oid = validate_object_id(order_id)
    order = order_repo.find_by_id(oid)
    if not order or (order["user_id"] != user_id and session.get("role") != "admin"):
        abort(404)

    file = request.files.get("proof")
    if not file or not file.filename:
        flash("Silakan pilih berkas bukti transfer terlebih dahulu.", "error")
        return render_template("user/order_detail.html", order=order), 422

    try:
        order = order_service.upload_payment_proof(order_id, user_id=user_id, file_storage=file)
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("user/order_detail.html", order=order), 422

    if request.is_json:
        return jsonify({"ok": True, "data": {"_id": str(order["_id"]), "payment_status": order["payment_status"]}}), 200

    flash("Bukti transfer berhasil diunggah! Mohon menunggu verifikasi admin.", "success")
    return redirect(url_for("orders.order_detail", order_id=order_id)), 302


@orders_bp.route("/orders/<order_id>/payment-proof", methods=["GET"])
@login_required
def get_payment_proof(order_id):
    """Menyajikan berkas bukti transfer hanya untuk pemilik order dan admin (Bab 16 & Keputusan Tambahan & TC-SC-06)."""
    import os
    from flask import send_from_directory

    user_id = ObjectId(session["user_id"])
    is_admin = session.get("role") == "admin"
    oid = validate_object_id(order_id, field_name="ID Order")
    order = order_repo.find_by_id(oid)

    # Hanya pemilik dan admin yang boleh mengakses (TC-SC-06)
    if not order or (not is_admin and order.get("user_id") != user_id):
        abort(404, description="Pesanan tidak ditemukan")

    proof_url = order.get("payment_proof")
    if not proof_url:
        abort(404, description="Bukti transfer belum diunggah")

    filename = os.path.basename(proof_url)
    upload_dir = os.path.abspath(os.path.join(current_app.config.get("UPLOAD_DIR", "instance/uploads"), "proofs"))
    return send_from_directory(upload_dir, filename)

