"""Route blueprint untuk manajemen pengguna oleh admin (Bab 14.6 Tambahan)."""
import re
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, session, abort
from ...utils.decorators import login_required, admin_required
from ...repositories import user_repo, audit_repo

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")

PER_PAGE = 20


@admin_users_bp.route("", methods=["GET"])
@login_required
@admin_required
def list_users():
    """Daftar pengguna dengan pencarian & filter role (Bab 14.6)."""
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    skip = (page - 1) * PER_PAGE

    query = {}
    if q:
        query["$or"] = [
            {"name": {"$regex": re.escape(q), "$options": "i"}},
            {"email": {"$regex": re.escape(q), "$options": "i"}},
        ]
    if role in ("admin", "user"):
        query["role"] = role

    total = user_repo.count(query)
    users = user_repo.find_all(query, skip=skip, limit=PER_PAGE)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    return render_template(
        "admin/users.html",
        active="users",
        users=users,
        q=q,
        role=role,
        page=page,
        total=total,
        total_pages=total_pages,
    )


@admin_users_bp.route("/<user_id>", methods=["PATCH"])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Aktifkan/nonaktifkan pengguna (Bab 14.6). Tidak boleh nonaktifkan diri sendiri."""
    user = user_repo.find_by_id(user_id)
    if not user:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Pengguna tidak ditemukan"}}), 404

    data = request.get_json(silent=True) or {}
    is_active = data.get("is_active")
    if is_active is None:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "Field is_active wajib"}}), 422

    is_active = bool(is_active)

    # Tidak boleh menonaktifkan diri sendiri
    if not is_active and str(user["_id"]) == session["user_id"]:
        return jsonify({"ok": False, "error": {"code": "forbidden", "message": "Tidak dapat menonaktifkan akun sendiri"}}), 403

    user_repo.update_profile(user["_id"], {"is_active": is_active})

    admin_id = ObjectId(session["user_id"])
    action = "user.activate" if is_active else "user.deactivate"
    audit_repo.log(
        actor_id=admin_id,
        action=action,
        entity_type="users",
        entity_id=user["_id"],
        after={"is_active": is_active},
    )

    status = "diaktifkan" if is_active else "dinonaktifkan"
    return jsonify({"ok": True, "data": {"message": f"Pengguna berhasil {status}"}}), 200

