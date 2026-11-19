"""Route blueprint untuk modul Notifikasi in-app (Bab 14.4)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, session
from ..utils.decorators import login_required
from ..repositories import notification_repo
from ..utils.validators import validate_object_id

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("", methods=["GET"])
@login_required
def list_notifications():
    """Halaman daftar notifikasi pengguna (Bab 14.4)."""
    user_id = ObjectId(session["user_id"])
    page = request.args.get("page", 1, type=int)
    per_page = 20
    skip = (page - 1) * per_page

    notifs = notification_repo.find_by_user(user_id, skip=skip, limit=per_page)

    if request.is_json:
        return jsonify({"ok": True, "data": notifs}), 200

    unread_count = notification_repo.count_unread(user_id)

    return render_template(
        "user/notifications.html",
        notifications=notifs,
        unread_count=unread_count,
        page=page,
    )


@notifications_bp.route("/<notif_id>/read", methods=["PATCH", "POST"])
@login_required
def mark_read(notif_id):
    """Menandai satu notifikasi sebagai dibaca (Bab 14.4)."""
    user_id = ObjectId(session["user_id"])
    nid = validate_object_id(notif_id, field_name="ID Notifikasi")

    res = notification_repo.mark_as_read(nid, user_id)
    if res.matched_count == 0:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Notifikasi tidak ditemukan"}}), 404

    return jsonify({"ok": True, "data": {"_id": str(nid), "is_read": True}}), 200


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    """Menandai seluruh notifikasi pengguna sebagai dibaca (Bab 14.4)."""
    user_id = ObjectId(session["user_id"])
    notification_repo.mark_all_as_read(user_id)

    return jsonify({"ok": True, "data": {"marked_all_read": True}}), 200

