"""Route blueprint untuk moderasi review oleh admin (Bab 14.6 Tambahan)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, session
from ...utils.decorators import login_required, admin_required
from ...repositories import review_repo, user_repo, product_repo, audit_repo

admin_reviews_bp = Blueprint("admin_reviews", __name__, url_prefix="/admin/reviews")

PER_PAGE = 20


@admin_reviews_bp.route("", methods=["GET"])
@login_required
@admin_required
def list_reviews():
    """Daftar semua review dengan filter visibilitas (Bab 14.6)."""
    vis = request.args.get("is_visible", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    skip = (page - 1) * PER_PAGE

    query = {}
    if vis == "1":
        query["is_visible"] = True
    elif vis == "0":
        query["is_visible"] = False

    total = review_repo.count(query)
    reviews = review_repo.find_all(query, skip=skip, limit=PER_PAGE)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    # Enrich: tambahkan nama user dan nama produk
    user_cache = {}
    product_cache = {}
    for r in reviews:
        uid = r.get("user_id")
        if uid and uid not in user_cache:
            u = user_repo.find_by_id(uid)
            user_cache[uid] = u["name"] if u else "Pengguna tidak dikenal"
        r["user_name"] = user_cache.get(uid, "-")

        pid = r.get("product_id")
        if pid and pid not in product_cache:
            p = product_repo.find_by_id(pid)
            product_cache[pid] = p["name"] if p else "Produk tidak dikenal"
        r["product_name"] = product_cache.get(pid, "-")

    return render_template(
        "admin/reviews.html",
        active="reviews",
        reviews=reviews,
        is_visible=vis,
        page=page,
        total=total,
        total_pages=total_pages,
    )


@admin_reviews_bp.route("/<review_id>", methods=["PATCH"])
@login_required
@admin_required
def toggle_review_visibility(review_id):
    """Toggle visibilitas review & recalculate rating produk (Bab 14.6)."""
    review = review_repo.find_by_id(review_id)
    if not review:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Review tidak ditemukan"}}), 404

    data = request.get_json(silent=True) or {}
    is_visible = data.get("is_visible")
    if is_visible is None:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "Field is_visible wajib"}}), 422

    is_visible = bool(is_visible)

    # Update visibilitas review
    review_repo.set_visibility(review["_id"], is_visible)

    # Recalculate rating produk
    rating_avg, rating_count = review_repo.calculate_product_rating(review["product_id"])
    product_repo.update_rating(review["product_id"], rating_avg, rating_count)

    # Audit log
    admin_id = ObjectId(session["user_id"])
    action = "review.show" if is_visible else "review.hide"
    audit_repo.log(
        actor_id=admin_id,
        action=action,
        entity_type="reviews",
        entity_id=review["_id"],
        after={"is_visible": is_visible, "rating_avg": rating_avg, "rating_count": rating_count},
    )

    status = "ditampilkan" if is_visible else "disembunyikan"
    return jsonify({"ok": True, "data": {"message": f"Review berhasil {status}"}}), 200

