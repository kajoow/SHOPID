"""Dekorator otorisasi RBAC (Bab 7.A, 14.1, 16.4)."""
from functools import wraps
from flask import session, request, redirect, url_for, abort, jsonify
from ..repositories import user_repo


def _is_json_request():
    return (
        request.is_json
        or request.path.startswith("/cart/items")
        or request.path.startswith("/wishlist/items")
        or request.method in ["PATCH", "DELETE"]
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def _login_redirect():
    endpoint = "admin.login" if request.path == "/admin" or request.path.startswith("/admin/") else "auth.login"
    return redirect(url_for(endpoint, next=request.path))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            if _is_json_request():
                return jsonify({"ok": False, "error": {"code": "unauthorized", "message": "Harap masuk terlebih dahulu"}}), 401
            return _login_redirect()

        user = user_repo.find_by_id(user_id)
        if not user or not user.get("is_active", True):
            session.clear()
            if _is_json_request():
                return jsonify({"ok": False, "error": {"code": "unauthorized", "message": "Akun tidak aktif atau tidak ditemukan"}}), 401
            return _login_redirect()

        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Memastikan user memiliki salah satu role yang diizinkan (default deny)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                if _is_json_request():
                    return jsonify({"ok": False, "error": {"code": "unauthorized", "message": "Harap masuk terlebih dahulu"}}), 401
                return _login_redirect()

            user = user_repo.find_by_id(user_id)
            if not user or not user.get("is_active", True):
                session.clear()
                if _is_json_request():
                    return jsonify({"ok": False, "error": {"code": "unauthorized", "message": "Akun tidak aktif"}}), 401
                return _login_redirect()

            user_role = user.get("role")
            if user_role not in allowed_roles:
                if _is_json_request():
                    return jsonify({
                        "ok": False,
                        "error": {
                            "code": "forbidden",
                            "message": f"Akses ditolak: role '{user_role}' tidak memiliki izin mengakses rute ini."
                        }
                    }), 403
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def customer_only(f):
    """Rute belanja khusus role user (Bab 1.3 D8). Admin mengakses rute pelanggan = 403."""
    return role_required("user")(f)


def admin_required(f):
    """Rute khusus role admin."""
    return role_required("admin")(f)

