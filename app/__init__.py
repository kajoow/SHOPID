"""Application factory untuk RetailBrain (Bab 8 & 18)."""
import os
import logging
from datetime import datetime
from flask import Flask, session, request, jsonify, render_template, redirect, url_for, send_from_directory
from flask.json.provider import DefaultJSONProvider
from flask_wtf.csrf import CSRFError
from bson import ObjectId

from .config import Config
from .extensions import init_extensions, csrf, limiter
from .commands import init_db_command, create_admin_command, seed_demo_command
from .utils.formatting import format_rupiah, format_datetime
from .utils.product_images import product_image_for
from .utils.validators import ValidationError
from .services.auth_service import ConflictError
from .repositories import user_repo, cart_repo

logger = logging.getLogger(__name__)


class MongoJSONProvider(DefaultJSONProvider):
    """Kustomisasi JSON encoder untuk mendukung ObjectId dan datetime MongoDB."""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class AnonymousUser:
    is_authenticated = False
    role = None
    name = "Tamu"
    _id = None
    id = None


def create_app(config_class=None):
    static_folder = None
    if os.environ.get("VERCEL") != "1":
        static_folder = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "public", "static")
        )
    app = Flask(__name__, static_folder=static_folder)

    # Custom JSON provider untuk serialisasi ObjectId & datetime
    app.json = MongoJSONProvider(app)

    # 1. Konfigurasi
    if config_class is None:
        config_class = Config
    app.config.from_object(config_class)

    # 2. Inisialisasi Ekstensi
    init_extensions(app)

    # 3. CLI Commands
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(seed_demo_command)

    # Helper deteksi request API/JSON
    def _is_api_request():
        return (
            request.is_json
            or request.path.startswith("/cart/items")
            or request.path.startswith("/wishlist/items")
            or request.method in ["PATCH", "DELETE"]
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
        )

    # CSRF Error handler khusus: status 403 (Bab 14.1 & TC-SC-01)
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        reason = getattr(e, "description", "CSRF token invalid")
        msg = f"Token CSRF tidak valid atau tidak disertakan ({reason})"
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "csrf_error", "message": msg}}), 403
        return render_template("base.html", error_message=msg), 403

    # 4. Context Processor Global & Template Filters (Bab 14.1)
    @app.context_processor
    def inject_global_vars():
        user_id = session.get("user_id")
        if user_id:
            user = user_repo.find_by_id(user_id)
            if user and user.get("is_active", True):
                current_user = {
                    "is_authenticated": True,
                    "role": user.get("role", "user"),
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "_id": user.get("_id"),
                    "id": str(user.get("_id")),
                }
                # Hitung jumlah item keranjang bila role user
                cart_count = cart_repo.get_cart_count(user["_id"]) if user.get("role") == "user" else 0
                return {"current_user": current_user, "cart_count": cart_count}

        return {"current_user": AnonymousUser(), "cart_count": 0}

    @app.template_filter("rp")
    def rp_filter(val):
        return format_rupiah(val)

    @app.template_filter("jkt_time")
    def jkt_time_filter(dt, fmt="%d %b %Y, %H:%M"):
        return format_datetime(dt, fmt)

    @app.template_filter("product_visual")
    def product_visual_filter(name):
        return f"/static/{product_image_for(name)}"

    @app.template_filter("datetime")
    def datetime_filter(dt, fmt="%d %b %Y, %H:%M"):
        return format_datetime(dt, fmt)

    # 5. Security Headers (Bab 16.1)
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content-Security-Policy disesuaikan dengan Google Fonts pada template
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: blob:; "
            "script-src 'self' 'unsafe-inline';"
        )
        return response

    # 6. Error Handlers Aman Tanpa Stack Trace (Bab 16.1)
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        msg = e.message
        code = getattr(e, "code", 422)
        if _is_api_request():
            err_code = "not_found" if code == 404 else ("bad_request" if code == 400 else "validation_error")
            return jsonify({"ok": False, "error": {"code": err_code, "message": msg, "field": e.field}}), code
        return render_template("base.html", error_message=msg), code

    @app.errorhandler(ConflictError)
    def handle_conflict_error_exception(e):
        msg = getattr(e, "message", "Terjadi konflik data atau stok")
        code = getattr(e, "code", 409)
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "conflict", "message": msg}}), code
        return render_template("base.html", error_message=msg), code

    @app.errorhandler(400)
    def bad_request_error(e):
        msg = getattr(e, "description", "Permintaan tidak valid")
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "bad_request", "message": msg}}), 400
        return render_template("base.html", error_message=msg), 400

    @app.errorhandler(401)
    def unauthorized_error(e):
        msg = getattr(e, "description", "Harap masuk terlebih dahulu")
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "unauthorized", "message": msg}}), 401
        return redirect(url_for("auth.login", next=request.path))

    @app.errorhandler(403)
    def forbidden_error(e):
        msg = getattr(e, "description", "Akses ditolak")
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "forbidden", "message": msg}}), 403
        return render_template("base.html", error_message=msg), 403

    @app.errorhandler(404)
    def not_found_error(e):
        msg = getattr(e, "description", "Sumber daya tidak ditemukan")
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "not_found", "message": msg}}), 404
        return render_template("base.html", error_message=msg), 404

    @app.errorhandler(409)
    def conflict_error(e):
        msg = getattr(e, "description", "Terjadi konflik data atau stok")
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "conflict", "message": msg}}), 409
        return render_template("base.html", error_message=msg), 409

    @app.errorhandler(422)
    def unprocessable_entity_error(e):
        msg = getattr(e, "description", "Validasi data gagal")
        fields = getattr(e, "fields", {})
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "validation_error", "message": msg, "fields": fields}}), 422
        return render_template("base.html", error_message=msg), 422

    @app.errorhandler(429)
    def ratelimit_handler(e):
        msg = "Terlalu banyak permintaan. Silakan tunggu beberapa saat."
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "too_many_requests", "message": msg}}), 429
        return render_template("base.html", error_message=msg), 429

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        msg = "Terjadi kesalahan pada sistem. Silakan coba lagi nanti."
        if _is_api_request():
            return jsonify({"ok": False, "error": {"code": "server_error", "message": msg}}), 500
        return render_template("base.html", error_message=msg), 500

    # 7. Route untuk menyajikan berkas upload publik (gambar produk dan profil)
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        # Mencegah akses ke subfolder proofs (Bab 16 & Keputusan Tambahan)
        if filename.startswith("proofs/"):
            return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Bukti transfer hanya dapat diakses lewat rute terautentikasi."}}), 403
        upload_base = os.path.abspath(app.config.get("UPLOAD_DIR", "instance/uploads"))
        return send_from_directory(upload_base, filename)

    # 8. Registrasi Blueprint awal
    from .routes import register_blueprints
    register_blueprints(app)

    return app
