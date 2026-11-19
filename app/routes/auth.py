"""Route blueprint untuk autentikasi: register, login, logout (Bab 14.2)."""
from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from ..services.auth_service import auth_service, AuthenticationError, ConflictError
from ..utils.validators import ValidationError
from ..extensions import limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _is_safe_url(target: str | None) -> bool:
    """Mencegah open redirect: hanya URL path relatif internal yang diizinkan (Bab 14.2)."""
    if not target:
        return False
    return target.startswith("/") and not target.startswith("//") and "\\" not in target


def _establish_session(user: dict) -> None:
    """Create a fresh authenticated session for a verified user."""
    session.clear()
    session["user_id"] = str(user["_id"])
    session["role"] = user["role"]
    session["name"] = user["name"]
    session.permanent = True

    lifetime_min = (
        current_app.config.get("ADMIN_SESSION_LIFETIME_MINUTES", 30)
        if user["role"] == "admin"
        else current_app.config.get("SESSION_LIFETIME_MINUTES", 120)
    )
    current_app.permanent_session_lifetime = timedelta(minutes=lifetime_min)


@auth_bp.route("/register", methods=["GET"])
def register():
    """Halaman form pendaftaran akun."""
    if session.get("user_id"):
        return redirect(url_for("products.home"))
    return render_template("auth/register.html")


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register_post():
    """Memproses pendaftaran akun pelanggan baru."""
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    phone = request.form.get("phone")

    try:
        auth_service.register_user(
            name=name,
            email=email,
            password=password,
            phone=phone,
        )
        flash("Pendaftaran berhasil. Silakan masuk.", "success")
        return redirect(url_for("auth.login")), 302
    except ConflictError as e:
        flash(e.message, "error")
        return render_template("auth/register.html"), 409
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("auth/register.html"), 422


@auth_bp.route("/login", methods=["GET"])
def login():
    """Halaman login pelanggan."""
    if session.get("user_id"):
        if session.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("products.home"))
    next_url = request.args.get("next", "")
    return render_template("auth/login.html", next=next_url)


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute; 20 per hour")
def login_post():
    """Memproses login pelanggan dengan proteksi session fixation dan pesan generik."""
    email = request.form.get("email")
    password = request.form.get("password")
    next_url = request.args.get("next") or request.form.get("next")

    try:
        user = auth_service.authenticate_user(email, password)
        if user["role"] != "user":
            raise AuthenticationError()
        _establish_session(user)

        flash(f"Selamat datang kembali, {user['name']}!", "success")

        if _is_safe_url(next_url) and next_url != "/admin" and not next_url.startswith("/admin/"):
            return redirect(next_url), 302

        return redirect(url_for("products.home")), 302

    except AuthenticationError as e:
        flash(e.message, "error")
        return render_template("auth/login.html", next=next_url), 401
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("auth/login.html", next=next_url), 422


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout dengan menghapus session di server dan mengosongkan cookie (Bab 7.A & TC-AU-10)."""
    session.clear()
    flash("Anda telah keluar dari akun.", "info")
    return redirect(url_for("products.home")), 302
