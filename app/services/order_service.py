"""Order service: Logika pembuatan order, mutasi status, verifikasi pembayaran, dan pembatalan atomik (Bab 7.D, 7.E, 11.4, 13.3)."""
import secrets
from datetime import datetime, timezone
from bson import ObjectId
from flask import current_app

from ..extensions import get_client
from ..repositories import (
    order_repo,
    cart_repo,
    product_repo,
    stock_repo,
    promotion_repo,
    audit_repo,
    notification_repo,
)
from ..models.enums import (
    OrderStatus,
    PaymentStatus,
    FulfillmentMethod,
    PaymentMethod,
    StockMovementType,
    StockReferenceType,
    NotificationType,
)
from ..utils.validators import (
    validate_string,
    validate_phone,
    validate_enum,
    validate_object_id,
    ValidationError,
)
from ..utils.uploads import save_upload_image
from .auth_service import ConflictError
from .promotion_service import promotion_service


def generate_order_number() -> str:
    """Format: RB-YYYYMMDD-NNNNNN (6 digit acak via modul secrets) (Bab 12.5 & Keputusan Tambahan)."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = "".join(str(secrets.randbelow(10)) for _ in range(6))
    return f"RB-{date_part}-{random_part}"


class OrderService:
    def create_order(
        self,
        user_id: ObjectId,
        contact_name: str,
        contact_phone: str,
        fulfillment_method: str,
        payment_method: str,
        idempotency_key: str,
        shipping_address_str: str | None = None,
        voucher_code: str | None = None,
    ) -> dict:
        """Membuat order baru dari keranjang belanja secara atomik (Bab 7.D, 13.3)."""
        # 1. Cek sifat Idempotent dari idempotency_key (TC-CO-07)
        valid_key = validate_string(idempotency_key, min_len=10, max_len=64, field_name="Idempotency key")
        existing_order = order_repo.find_by_idempotency_key(valid_key)
        if existing_order:
            return existing_order

        # 2. Validasi keranjang belanja tidak kosong (TC-CO-03)
        cart = cart_repo.find_by_user_id(user_id)
        if not cart or not cart.get("items"):
            raise ValidationError("Keranjang belanja kosong", code=400)

        # 3. Validasi kontak dan pengiriman
        valid_contact_name = validate_string(contact_name, min_len=2, max_len=100, field_name="Nama penerima")
        valid_contact_phone = validate_phone(contact_phone)
        if not valid_contact_phone:
            raise ValidationError("Nomor telepon penerima wajib diisi", field="contact_phone", code=422)

        valid_fulfillment = validate_enum(fulfillment_method, FulfillmentMethod.ALL, field_name="Metode pengambilan")
        valid_payment_method = validate_enum(payment_method, PaymentMethod.ALL, field_name="Metode pembayaran")

        # Snapshot kontak
        contact_snapshot = {
            "name": valid_contact_name,
            "phone": valid_contact_phone,
        }

        # Snapshot alamat
        shipping_address_snapshot = None
        delivery_fee = 0
        if valid_fulfillment == FulfillmentMethod.DELIVERY:
            if not shipping_address_str or not shipping_address_str.strip():
                raise ValidationError("Alamat pengiriman wajib diisi untuk metode delivery", field="shipping_address", code=422)
            clean_addr = validate_string(shipping_address_str, min_len=5, max_len=300, field_name="Alamat pengiriman")
            shipping_address_snapshot = {
                "recipient": valid_contact_name,
                "line": clean_addr,
                "city": None,
                "postal_code": None,
                "notes": None,
            }
            delivery_fee = current_app.config.get("DELIVERY_FEE", 10000)

        # 4. Ambil dan validasi produk terkini dari master_product (Server recomputes, TC-CO-04)
        items_snapshot = []
        subtotal = 0
        for item in cart["items"]:
            prod = product_repo.find_by_id(item["product_id"])
            if not prod or not prod.get("is_active", True):
                raise ConflictError(f"Produk '{item.get('product_id')}' sudah tidak tersedia.")

            qty = item["quantity"]
            if prod.get("stock", 0) < qty:
                raise ConflictError(f"Stok untuk '{prod['name']}' tidak mencukupi (sisa: {prod.get('stock', 0)}).")

            unit_price = prod["price"]
            line_total = unit_price * qty
            subtotal += line_total

            items_snapshot.append({
                "product_id": prod["_id"],
                "sku": prod["sku"],
                "name": prod["name"],
                "unit_price": unit_price,
                "quantity": qty,
                "line_total": line_total,
            })

        # 5. Validasi Voucher
        discount = 0
        applied_voucher_code = None
        if voucher_code and voucher_code.strip():
            discount, _ = promotion_service.validate_and_calculate_discount(voucher_code, subtotal)
            applied_voucher_code = voucher_code.strip().upper()

        total = max(0, subtotal - discount + delivery_fee)

        # 6. Eksekusi Transaksi Multi-Dokumen MongoDB (Bab 13.3)
        client = get_client()
        is_repl_set = current_app.config.get("IS_REPLICA_SET", True)

        now = datetime.now(timezone.utc)
        order_id = ObjectId()
        order_number = generate_order_number()

        order_doc = {
            "_id": order_id,
            "order_number": order_number,
            "user_id": user_id,
            "items": items_snapshot,
            "subtotal": subtotal,
            "discount": discount,
            "delivery_fee": delivery_fee,
            "total": total,
            "fulfillment_method": valid_fulfillment,
            "payment_method": valid_payment_method,
            "payment_status": PaymentStatus.UNPAID,
            "order_status": OrderStatus.PENDING,
            "contact": contact_snapshot,
            "shipping_address": shipping_address_snapshot,
            "voucher_code": applied_voucher_code,
            "payment_proof": None,
            "status_history": [
                {
                    "from": None,
                    "to": OrderStatus.PENDING,
                    "actor_id": user_id,
                    "at": now,
                    "note": "Order dibuat",
                }
            ],
            "idempotency_key": valid_key,
            "created_at": now,
            "updated_at": now,
        }

        if is_repl_set:
            try:
                with client.start_session() as s:
                    with s.start_transaction():
                        self._execute_order_operations(s, user_id, order_doc, items_snapshot, applied_voucher_code)
            except Exception as e:
                if isinstance(e, (ConflictError, ValidationError)):
                    raise e
                raise Exception(f"Gagal memproses order dalam transaksi: {e}")
        else:
            self._execute_order_with_compensation(user_id, order_doc, items_snapshot, applied_voucher_code)

        return order_doc

    def _execute_order_operations(
        self,
        session,
        user_id: ObjectId,
        order_doc: dict,
        items_snapshot: list,
        voucher_code: str | None,
    ):
        for item in items_snapshot:
            pid = item["product_id"]
            qty = item["quantity"]
            prod = product_repo.find_by_id(pid)
            before = prod["stock"] if prod else 0

            res = product_repo.dec_stock_if_enough(pid, qty, session=session)
            if res.matched_count == 0:
                raise ConflictError(f"Stok untuk '{item['name']}' tidak mencukupi (terjadi perebutan stok).")

            after = before - qty
            stock_repo.insert(
                product_id=pid,
                movement_type=StockMovementType.REDUCTION,
                quantity=-qty,
                before_stock=before,
                after_stock=after,
                reference_type=StockReferenceType.ORDER,
                reference_id=order_doc["_id"],
                actor_id=user_id,
                note=f"Pengurangan stok untuk order {order_doc['order_number']}",
                session=session,
            )

        if voucher_code:
            v_res = promotion_repo.inc_used_if_quota(voucher_code, session=session)
            if v_res.matched_count == 0:
                raise ConflictError(f"Kuota voucher '{voucher_code}' telah habis saat pemrosesan.")

        for _ in range(3):
            try:
                order_repo.insert(order_doc, session=session)
                break
            except Exception as e:
                if "duplicate key" in str(e).lower() or "e11000" in str(e).lower():
                    order_doc["order_number"] = generate_order_number()
                else:
                    raise e
        else:
            raise Exception("Gagal menghasilkan nomor order unik.")

        cart_repo.clear(user_id, session=session)

        audit_repo.log(
            actor_id=user_id,
            action="order.create",
            entity_type="orders",
            entity_id=order_doc["_id"],
            after={"order_number": order_doc["order_number"], "total": order_doc["total"]},
            session=session,
        )

    def _execute_order_with_compensation(
        self,
        user_id: ObjectId,
        order_doc: dict,
        items_snapshot: list,
        voucher_code: str | None,
    ):
        compensated_items = []
        voucher_incremented = False

        try:
            for item in items_snapshot:
                pid = item["product_id"]
                qty = item["quantity"]
                prod = product_repo.find_by_id(pid)
                before = prod["stock"] if prod else 0

                res = product_repo.dec_stock_if_enough(pid, qty)
                if res.matched_count == 0:
                    raise ConflictError(f"Stok untuk '{item['name']}' tidak mencukupi.")

                after = before - qty
                stock_repo.insert(
                    product_id=pid,
                    movement_type=StockMovementType.REDUCTION,
                    quantity=-qty,
                    before_stock=before,
                    after_stock=after,
                    reference_type=StockReferenceType.ORDER,
                    reference_id=order_doc["_id"],
                    actor_id=user_id,
                    note=f"Pengurangan stok untuk order {order_doc['order_number']}",
                )
                compensated_items.append((pid, qty))

            if voucher_code:
                v_res = promotion_repo.inc_used_if_quota(voucher_code)
                if v_res.matched_count == 0:
                    raise ConflictError(f"Kuota voucher '{voucher_code}' telah habis.")
                voucher_incremented = True

            order_repo.insert(order_doc)
            cart_repo.clear(user_id)

            audit_repo.log(
                actor_id=user_id,
                action="order.create",
                entity_type="orders",
                entity_id=order_doc["_id"],
                after={"order_number": order_doc["order_number"], "total": order_doc["total"]},
            )

        except Exception as e:
            for pid, qty in compensated_items:
                product_repo.inc_stock(pid, qty)
            if voucher_incremented and voucher_code:
                promotion_repo.dec_used_count(voucher_code)
            raise e

    def cancel_order(
        self,
        order_id: ObjectId | str,
        actor_id: ObjectId,
        is_admin: bool = False,
        note: str | None = None,
    ) -> dict:
        """Pembatalan order: pulihkan stok, status payment, voucher, dan catat riwayat (Bab 7.E, TC-OR-09..14)."""
        oid = validate_object_id(order_id, field_name="ID Order")
        order = order_repo.find_by_id(oid)
        if not order:
            raise ValidationError("Pesanan tidak ditemukan", code=404)

        current_status = order.get("order_status")

        # Validasi hak pembatalan dan status asal
        if not is_admin:
            if order.get("user_id") != actor_id:
                raise ValidationError("Pesanan tidak ditemukan", code=404)
            if current_status != OrderStatus.PENDING:
                raise ConflictError("Hanya pesanan berstatus pending yang dapat dibatalkan oleh pelanggan.", code=409)
        else:
            if current_status in OrderStatus.TERMINAL:
                raise ConflictError(f"Pesanan dengan status '{current_status}' tidak dapat dibatalkan.", code=409)

        # Penyesuaian payment_status saat batal (Keputusan Tambahan & Bab 7.E):
        # paid -> refunded; awaiting_verification -> failed; unpaid tetap unpaid
        current_pay_status = order.get("payment_status", PaymentStatus.UNPAID)
        if current_pay_status == PaymentStatus.PAID:
            new_pay_status = PaymentStatus.REFUNDED
        elif current_pay_status == PaymentStatus.AWAITING_VERIFICATION:
            new_pay_status = PaymentStatus.FAILED
        else:
            new_pay_status = current_pay_status

        clean_note = validate_string(note, max_len=200, field_name="Catatan pembatalan") if note else "Pesanan dibatalkan"

        client = get_client()
        is_repl_set = current_app.config.get("IS_REPLICA_SET", True)

        def _do_cancel(session=None):
            # 1. Update bersyarat {_id, order_status: current_status}
            res = order_repo.update_status_conditional(
                order_id=oid,
                from_status=current_status,
                to_status=OrderStatus.CANCELLED,
                actor_id=actor_id,
                note=clean_note,
                session=session,
            )
            if res.matched_count == 0:
                raise ConflictError("Status pesanan telah berubah oleh proses lain.", code=409)

            # 2. Update payment_status bila berubah
            if new_pay_status != current_pay_status:
                order_repo.update_payment_status(
                    order_id=oid,
                    payment_status=new_pay_status,
                    actor_id=actor_id,
                    note=f"Status pembayaran disesuaikan karena pesanan dibatalkan ({clean_note})",
                    session=session,
                )

            # 3. Pulihkan stok untuk setiap item & buat record stock_movements restoration (TC-OR-09..12)
            for item in order.get("items", []):
                pid = item["product_id"]
                qty = item["quantity"]
                prod = product_repo.find_by_id(pid)
                before_stock = prod["stock"] if prod else 0

                product_repo.inc_stock(pid, qty, session=session)
                after_stock = before_stock + qty

                stock_repo.insert(
                    product_id=pid,
                    movement_type=StockMovementType.RESTORATION,
                    quantity=qty,
                    before_stock=before_stock,
                    after_stock=after_stock,
                    reference_type=StockReferenceType.ORDER,
                    reference_id=oid,
                    actor_id=actor_id,
                    note=f"Pemulihan stok pesanan {order['order_number']}",
                    session=session,
                )

            # 4. Kembalikan kuota voucher jika order memakai voucher (TC-OR-14)
            voucher_code = order.get("voucher_code")
            if voucher_code:
                promotion_repo.dec_used_count(voucher_code, session=session)

            # 5. Audit log
            audit_repo.log(
                actor_id=actor_id,
                action="order.cancel",
                entity_type="orders",
                entity_id=oid,
                before={"order_status": current_status, "payment_status": current_pay_status},
                after={"order_status": OrderStatus.CANCELLED, "payment_status": new_pay_status},
                session=session,
            )

        if is_repl_set:
            try:
                with client.start_session() as s:
                    with s.start_transaction():
                        _do_cancel(session=s)
            except Exception as e:
                if isinstance(e, (ConflictError, ValidationError)):
                    raise e
                raise Exception(f"Gagal membatalkan order dalam transaksi: {e}")
        else:
            _do_cancel()

        # In-app notification
        notification_repo.insert(
            user_id=order["user_id"],
            title="Pesanan Dibatalkan",
            message=f"Pesanan {order['order_number']} telah dibatalkan ({clean_note}).",
            notif_type=NotificationType.ORDER_STATUS,
            reference_id=oid,
        )

        return order_repo.find_by_id(oid)

    def transition_order_status(
        self,
        order_id: ObjectId | str,
        to_status: str,
        actor_id: ObjectId,
        note: str | None = None,
    ) -> dict:
        """Transisi status order oleh admin dengan validasi diagram Bab 7.E (TC-OR-01..05)."""
        oid = validate_object_id(order_id, field_name="ID Order")
        order = order_repo.find_by_id(oid)
        if not order:
            raise ValidationError("Pesanan tidak ditemukan", code=404)

        current_status = order.get("order_status")
        valid_to_status = validate_enum(to_status, OrderStatus.ALL, field_name="Status tujuan")

        # Jika to_status adalah cancelled, gunakan cancel_order
        if valid_to_status == OrderStatus.CANCELLED:
            return self.cancel_order(oid, actor_id=actor_id, is_admin=True, note=note)

        # Matriks transisi yang diizinkan (Bab 7.E)
        ALLOWED_TRANSITIONS = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED],
            OrderStatus.CONFIRMED: [OrderStatus.PROCESSING],
            OrderStatus.PROCESSING: [OrderStatus.READY_FOR_PICKUP],
            OrderStatus.READY_FOR_PICKUP: [OrderStatus.COMPLETED],
        }

        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        if valid_to_status not in allowed:
            raise ConflictError(
                f"Transisi status dari '{current_status}' ke '{valid_to_status}' tidak diizinkan.",
                code=409,
            )

        # Syarat transisi (Bab 7.E & TC-OR-04, TC-OR-05)
        if valid_to_status == OrderStatus.PROCESSING:
            if order.get("payment_method") == PaymentMethod.BANK_TRANSFER and order.get("payment_status") != PaymentStatus.PAID:
                raise ConflictError("Pesanan transfer bank belum lunas, tidak dapat diubah ke processing.", code=409)

        if valid_to_status == OrderStatus.COMPLETED:
            if order.get("payment_status") != PaymentStatus.PAID:
                raise ConflictError("Pesanan belum lunas, tidak dapat diselesaikan.", code=409)

        clean_note = validate_string(note, max_len=200, field_name="Catatan") if note else None

        # Update bersyarat {_id, order_status: current_status}
        res = order_repo.update_status_conditional(
            order_id=oid,
            from_status=current_status,
            to_status=valid_to_status,
            actor_id=actor_id,
            note=clean_note,
        )
        if res.matched_count == 0:
            raise ConflictError("Status pesanan telah diperbarui oleh proses lain.", code=409)

        # Efek samping completed: sold_count produk bertambah (Bab 7.E & TC-OR-15)
        if valid_to_status == OrderStatus.COMPLETED:
            for item in order.get("items", []):
                product_repo.inc_sold_count(item["product_id"], item["quantity"])

        # Audit log
        audit_repo.log(
            actor_id=actor_id,
            action="order.status_update",
            entity_type="orders",
            entity_id=oid,
            before={"order_status": current_status},
            after={"order_status": valid_to_status, "note": clean_note},
        )

        # In-app notifikasi
        notification_repo.insert(
            user_id=order["user_id"],
            title=f"Status Pesanan: {valid_to_status.replace('_', ' ').capitalize()}",
            message=f"Status pesanan {order['order_number']} diperbarui menjadi {valid_to_status.replace('_', ' ')}.",
            notif_type=NotificationType.ORDER_STATUS,
            reference_id=oid,
        )

        return order_repo.find_by_id(oid)

    def upload_payment_proof(
        self,
        order_id: ObjectId | str,
        user_id: ObjectId,
        file_storage,
    ) -> dict:
        """Unggah bukti transfer pembayaran oleh pelanggan (Bab 7.E & TC-OR-06, TC-OR-07)."""
        oid = validate_object_id(order_id, field_name="ID Order")
        order = order_repo.find_by_id(oid)
        if not order or order.get("user_id") != user_id:
            raise ValidationError("Pesanan tidak ditemukan", code=404)

        if order.get("payment_method") != PaymentMethod.BANK_TRANSFER:
            raise ConflictError("Metode pembayaran pesanan ini bukan transfer bank.", code=409)

        if order.get("payment_status") not in [PaymentStatus.UNPAID, PaymentStatus.FAILED]:
            raise ConflictError(
                f"Bukti transfer tidak dapat diunggah untuk status pembayaran '{order.get('payment_status')}'.",
                code=409,
            )

        # Simpan gambar bukti transfer secara aman (subfolder 'proofs')
        proof_url = save_upload_image(file_storage, subfolder="proofs")

        # Update order: payment_proof dan payment_status = awaiting_verification
        order_repo.set_payment_proof(oid, proof_url)

        # Tambahkan ke status history
        order_repo.update_payment_status(
            order_id=oid,
            payment_status=PaymentStatus.AWAITING_VERIFICATION,
            actor_id=user_id,
            note="Bukti transfer diunggah pelanggan",
        )

        # Audit log
        audit_repo.log(
            actor_id=user_id,
            action="payment.upload_proof",
            entity_type="orders",
            entity_id=oid,
            before={"payment_status": order.get("payment_status")},
            after={"payment_status": PaymentStatus.AWAITING_VERIFICATION, "proof": proof_url},
        )

        return order_repo.find_by_id(oid)

    def verify_payment(
        self,
        order_id: ObjectId | str,
        actor_id: ObjectId,
        action: str,
        note: str | None = None,
    ) -> dict:
        """Verifikasi / penolakan pembayaran bank atau pencatatan lunas COD oleh admin (Bab 7.E & TC-OR-08)."""
        oid = validate_object_id(order_id, field_name="ID Order")
        order = order_repo.find_by_id(oid)
        if not order:
            raise ValidationError("Pesanan tidak ditemukan", code=404)

        current_pay_status = order.get("payment_status")
        clean_note = validate_string(note, max_len=200, field_name="Catatan") if note else None

        if action == "verify":
            if current_pay_status != PaymentStatus.AWAITING_VERIFICATION:
                raise ConflictError(
                    f"Pembayaran berstatus '{current_pay_status}' tidak dalam antrean verifikasi.",
                    code=409,
                )
            new_pay_status = PaymentStatus.PAID
            status_note = clean_note or "Pembayaran diverifikasi oleh admin"
            notif_msg = f"Pembayaran untuk pesanan {order['order_number']} telah diverifikasi dan dinyatakan LUNAS."

        elif action == "reject":
            if current_pay_status != PaymentStatus.AWAITING_VERIFICATION:
                raise ConflictError(
                    f"Pembayaran berstatus '{current_pay_status}' tidak dapat ditolak.",
                    code=409,
                )
            new_pay_status = PaymentStatus.FAILED
            status_note = clean_note or "Bukti transfer ditolak admin"
            notif_msg = f"Bukti transfer pesanan {order['order_number']} ditolak. Catatan: {status_note}"

        elif action == "mark_cod_paid":
            if order.get("payment_method") != PaymentMethod.COD:
                raise ConflictError("Hanya pesanan COD yang dapat ditandai lunas tunai.", code=409)
            if current_pay_status != PaymentStatus.UNPAID:
                raise ConflictError(
                    f"Pembayaran COD sudah berstatus '{current_pay_status}'.",
                    code=409,
                )
            new_pay_status = PaymentStatus.PAID
            status_note = clean_note or "Pembayaran COD diterima saat serah terima barang"
            notif_msg = f"Pembayaran tunai pesanan {order['order_number']} telah diterima."

        else:
            raise ValidationError(f"Aksi pembayaran '{action}' tidak valid", field="action", code=422)

        order_repo.update_payment_status(
            order_id=oid,
            payment_status=new_pay_status,
            actor_id=actor_id,
            note=status_note,
        )

        audit_repo.log(
            actor_id=actor_id,
            action="payment.update",
            entity_type="orders",
            entity_id=oid,
            before={"payment_status": current_pay_status},
            after={"payment_status": new_pay_status, "action": action, "note": status_note},
        )

        notification_repo.insert(
            user_id=order["user_id"],
            title="Pembaruan Status Pembayaran",
            message=notif_msg,
            notif_type=NotificationType.PAYMENT,
            reference_id=oid,
        )

        return order_repo.find_by_id(oid)


order_service = OrderService()
