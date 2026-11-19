"""Route blueprint untuk ulasan dan rating produk pelanggan (Bab 14.4 & TC-RV-01..03)."""
from bson import ObjectId
from flask import Blueprint, request, jsonify, session
from ..utils.decorators import login_required, customer_only
from ..repositories import review_repo, order_repo, product_repo
from ..models.enums import OrderStatus
from ..utils.validators import validate_object_id, validate_string, ValidationError
from ..services.auth_service import ConflictError

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.route("/products/<product_id>/reviews", methods=["POST"])
@login_required
@customer_only
def create_review(product_id):
    """Kirim review produk setelah pesanan completed (Bab 14.4 & TC-RV-01..03)."""
    user_id = ObjectId(session["user_id"])
    pid = validate_object_id(product_id, field_name="ID Produk")

    data = request.get_json(silent=True) or request.form
    raw_order_id = data.get("order_id")
    if not raw_order_id:
        raise ValidationError("ID Order wajib disertakan", field="order_id", code=422)

    oid = validate_object_id(raw_order_id, field_name="ID Order")
    order = order_repo.find_by_id(oid)

    # TC-RV-02: Review tanpa pembelian selesai / bukan milik user -> 403
    if not order or order.get("user_id") != user_id:
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Pesanan tidak ditemukan atau bukan milik Anda"}}), 403

    if order.get("order_status") != OrderStatus.COMPLETED:
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Ulasan hanya dapat diberikan untuk pesanan yang telah selesai"}}), 403

    # Cek apakah produk benar-benar dibeli dalam order ini
    bought_product_ids = [item["product_id"] for item in order.get("items", [])]
    if pid not in bought_product_ids:
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Produk ini tidak terdapat dalam pesanan tersebut"}}), 403

    # TC-RV-03: Satu review per produk per order -> 409 bila ganda
    existing_review = review_repo.collection.find_one({"order_id": oid, "product_id": pid})
    if existing_review:
        raise ConflictError("Anda sudah memberikan ulasan untuk produk ini pada pesanan yang sama.", code=409)

    try:
        rating = int(data.get("rating", 5))
        if rating < 1 or rating > 5:
            raise ValidationError("Rating harus bernilai 1 sampai 5", field="rating", code=422)
    except (ValueError, TypeError):
        raise ValidationError("Rating harus berupa angka 1-5", field="rating", code=422)

    raw_comment = data.get("comment")
    comment = validate_string(raw_comment, max_len=1000, field_name="Komentar") if raw_comment else None

    # Simpan review
    review_id = review_repo.insert(
        user_id=user_id,
        product_id=pid,
        order_id=oid,
        rating=rating,
        comment=comment,
        is_visible=True,
    )

    # Hitung rata-rata rating baru produk secara atomik
    pipeline = [
        {"$match": {"product_id": pid, "is_visible": True}},
        {"$group": {"_id": "$product_id", "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    agg_res = list(review_repo.collection.aggregate(pipeline))
    if agg_res:
        new_avg = round(float(agg_res[0]["avg"]), 1)
        new_count = int(agg_res[0]["count"])
        product_repo.update_rating(pid, new_avg, new_count)

    return jsonify({
        "ok": True,
        "data": {
            "_id": str(review_id),
            "product_id": str(pid),
            "rating": rating,
        }
    }), 201


@reviews_bp.route("/products/<product_id>/reviews", methods=["GET"])
def list_product_reviews(product_id):
    """Mendapatkan daftar review publik suatu produk."""
    pid = validate_object_id(product_id, field_name="ID Produk")
    reviews = review_repo.find_by_product(pid, only_visible=True)
    return jsonify({"ok": True, "data": reviews}), 200

