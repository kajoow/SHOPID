"""Route blueprint untuk katalog publik dan detail produk (Bab 14.3)."""
from datetime import datetime, timezone
from bson import ObjectId
from flask import Blueprint, render_template, request, session
from ..services.catalog_service import catalog_service
from ..repositories import category_repo, review_repo, user_repo, order_repo, promotion_repo
from ..models.enums import OrderStatus

products_bp = Blueprint("products", __name__)


@products_bp.route("/", methods=["GET"])
def home():
    """Halaman Beranda: kategori aktif dan produk terbaru (Bab 14.2 & 15.2)."""
    categories = category_repo.find_all({"is_active": True})
    products, _, _ = catalog_service.get_public_products(page=1, per_page=8)
    category_slugs = {str(category["_id"]): category["slug"] for category in categories}
    for product in products:
        product["category_slug"] = category_slugs.get(str(product.get("category_id")), "")
    recommendations = catalog_service.get_best_selling_products(limit=3)
    now = datetime.now(timezone.utc)
    promotions = promotion_repo.find_all(
        {
            "is_active": True,
            "starts_at": {"$lte": now},
            "ends_at": {"$gte": now},
            "$expr": {"$lt": ["$used_count", "$quota"]},
        },
        limit=8,
    )
    return render_template(
        "public/home.html",
        categories=categories,
        products=products,
        recommendations=recommendations,
        promotions=promotions,
    )


@products_bp.route("/products", methods=["GET"])
def catalog():
    """Katalog produk aktif dengan filter, pencarian, sort, dan paginasi (Bab 14.3)."""
    q = request.args.get("q")
    category = request.args.get("category")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    sort = request.args.get("sort")
    page = request.args.get("page", 1, type=int)

    categories = category_repo.find_all({"is_active": True})
    products, total_count, total_pages = catalog_service.get_public_products(
        q=q,
        category_slug=category,
        min_price=min_price if min_price else None,
        max_price=max_price if max_price else None,
        sort=sort,
        page=page,
        per_page=20,
    )

    return render_template(
        "public/catalog.html",
        categories=categories,
        products=products,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )


@products_bp.route("/products/<product_id>", methods=["GET"])
def detail(product_id):
    """Detail produk aktif berdasarkan ObjectId (Bab 14.3 & TC-VA-01, TC-PR-05)."""
    product = catalog_service.get_product_detail(product_id)
    pid = product["_id"]

    # Ambil daftar review yang disetujui/tampil (is_visible=True)
    reviews = review_repo.find_by_product(pid, only_visible=True)

    # Enrich ulasan dengan nama pelanggan
    user_cache = {}
    for r in reviews:
        uid = r.get("user_id")
        if uid and uid not in user_cache:
            u = user_repo.find_by_id(uid)
            user_cache[uid] = u["name"] if u else "Pelanggan"
        r["user_name"] = user_cache.get(uid, "Pelanggan")

    # Cek apakah user login memiliki pesanan yang completed dan belum memberikan ulasan
    eligible_order_id = None
    user_id_str = session.get("user_id")
    if user_id_str:
        try:
            uid = ObjectId(user_id_str)
            completed_orders = order_repo.find_all({
                "user_id": uid,
                "order_status": OrderStatus.COMPLETED,
                "items.product_id": pid,
            })
            for o in completed_orders:
                already_reviewed = review_repo.collection.find_one({
                    "order_id": o["_id"],
                    "product_id": pid,
                })
                if not already_reviewed:
                    eligible_order_id = str(o["_id"])
                    break
        except Exception:
            pass

    return render_template(
        "public/product_detail.html",
        product=product,
        reviews=reviews,
        eligible_order_id=eligible_order_id,
    )
