"""Route blueprint untuk dashboard admin dan laporan analitik (Bab 7.H, 14.5, 14.6)."""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from ...extensions import limiter
from ...services.auth_service import auth_service, AuthenticationError
from ...utils.validators import ValidationError
from ...utils.decorators import login_required, admin_required
from ...services.report_service import report_service
from ..auth import _establish_session, _is_safe_url
from .products import admin_products_bp
from .categories import admin_categories_bp
from .orders import admin_orders_bp
from .inventory import admin_inventory_bp
from .promotions import admin_promotions_bp
from .audit_logs import admin_audit_bp
from .users import admin_users_bp
from .reviews import admin_reviews_bp

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

__all__ = [
    "admin_bp",
    "admin_products_bp",
    "admin_categories_bp",
    "admin_orders_bp",
    "admin_inventory_bp",
    "admin_promotions_bp",
    "admin_audit_bp",
    "admin_users_bp",
    "admin_reviews_bp",
]


@admin_bp.route("/login", methods=["GET"])
def login():
    """Halaman login terpisah untuk akun admin."""
    if session.get("user_id") and session.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html", next=request.args.get("next", ""))


@admin_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute; 20 per hour")
def login_post():
    """Memproses login admin saja."""
    email = request.form.get("email")
    password = request.form.get("password")
    next_url = request.args.get("next") or request.form.get("next")

    try:
        user = auth_service.authenticate_user(email, password)
        if user["role"] != "admin":
            raise AuthenticationError()
        _establish_session(user)
        flash(f"Selamat datang, {user['name']}!", "success")

        if (
            _is_safe_url(next_url)
            and next_url.startswith("/admin/")
            and not next_url.startswith("/admin/login")
        ):
            return redirect(next_url), 302
        return redirect(url_for("admin.dashboard")), 302
    except AuthenticationError as e:
        flash(e.message, "error")
        return render_template("admin/login.html", next=next_url), 401
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("admin/login.html", next=next_url), 422


@admin_bp.route("/dashboard", methods=["GET"])
@login_required
@admin_required
def dashboard():
    """Halaman ringkasan eksekutif (dashboard) admin dengan metrik real-time (Bab 7.H, 14.5)."""
    data = report_service.get_dashboard_summary()
    return render_template(
        "admin/dashboard.html",
        active="dashboard",
        kpi=data["kpi"],
        pending_orders=data["pending_orders"],
        low_stock=data["low_stock"],
    )


@admin_bp.route("/reports/sales", methods=["GET"])
@login_required
@admin_required
def sales_report():
    """Laporan penjualan harian zona waktu Asia/Jakarta dari order completed (Bab 7.H, 14.6 & TC-RP-01..02)."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    report_data = report_service.get_sales_report(from_date=from_date, to_date=to_date)

    if request.is_json or "application/json" in request.headers.get("Accept", "") or request.args.get("format") == "json":
        return jsonify({"ok": True, "data": report_data}), 200

    return render_template(
        "admin/reports_sales.html",
        active="reports/sales",
        report=report_data,
        from_date=from_date or "",
        to_date=to_date or "",
    )


@admin_bp.route("/reports/inventory", methods=["GET"])
@login_required
@admin_required
def inventory_report():
    """Laporan status dan valuasi inventori dari database master_product (Bab 7.H, 14.6)."""
    report_data = report_service.get_inventory_report()

    if request.is_json or "application/json" in request.headers.get("Accept", "") or request.args.get("format") == "json":
        return jsonify({"ok": True, "data": report_data}), 200

    return render_template(
        "admin/reports_inventory.html",
        active="reports/sales",
        report=report_data,
    )
