"""Route blueprint untuk profil dan dashboard pelanggan (Bab 14.2)."""
from bson import ObjectId
from flask import Blueprint, render_template, request, session, jsonify, flash, redirect, url_for
from ..utils.decorators import login_required, customer_only
from ..services.auth_service import auth_service, AuthenticationError
from ..utils.validators import ValidationError
from ..utils.uploads import save_upload_image
from ..repositories import user_repo, order_repo

user_bp = Blueprint("user", __name__)


def _profile_completion(user):
    fields = ("name", "email", "phone", "address", "profile_image")
    return round(sum(bool(user.get(field)) for field in fields) / len(fields) * 100)


@user_bp.route("/dashboard", methods=["GET"])
@login_required
@customer_only
def dashboard():
    """Halaman dashboard pelanggan (Bab 14.2)."""
    user_id = ObjectId(session["user_id"])
    user = user_repo.find_by_id(user_id)
    recent_orders = order_repo.find_all({"user_id": user_id}, sort_list=[("created_at", -1)], limit=3)
    return render_template("user/dashboard.html", user=user, recent_orders=recent_orders)


@user_bp.route("/profile", methods=["GET"])
@login_required
@customer_only
def profile():
    """Halaman lihat profil pelanggan (Bab 14.2)."""
    user_id = ObjectId(session["user_id"])
    user = user_repo.find_by_id(user_id)
    return render_template(
        "user/profile.html",
        user=user,
        profile_completion=_profile_completion(user),
    )


@user_bp.route("/profile/photo", methods=["POST"])
@login_required
@customer_only
def upload_profile_photo():
    """Unggah foto profil pelanggan."""
    user_id = ObjectId(session["user_id"])
    try:
        image_url = save_upload_image(request.files.get("profile_image"), subfolder="profiles")
        if not user_repo.update_profile(user_id, {"profile_image": image_url}):
            raise ValidationError("Profil tidak ditemukan.", code=404)
    except ValidationError as e:
        flash(e.message, "error")
        return redirect(url_for("user.profile"))

    flash("Foto profil berhasil diperbarui.", "success")
    return redirect(url_for("user.profile"))


@user_bp.route("/profile", methods=["PATCH", "POST"])
@login_required
@customer_only
def update_profile():
    """Ubah profil nama, telepon, dan alamat (Bab 14.2)."""
    user_id = ObjectId(session["user_id"])
    data = request.get_json(silent=True) or request.form

    name = data.get("name")
    phone = data.get("phone")
    address = data.get("address")

    try:
        updated_user = auth_service.update_profile(
            user_id=user_id,
            name=name,
            phone=phone,
            address=address,
        )
        session["name"] = updated_user["name"]

        if request.is_json:
            return jsonify({"ok": True, "data": updated_user}), 200

        flash("Profil berhasil diperbarui.", "success")
        return redirect(url_for("user.profile")), 302
    except ValidationError as e:
        if request.is_json:
            return jsonify({"ok": False, "error": {"code": "validation_error", "message": e.message, "field": e.field}}), 422
        flash(e.message, "error")
        user = user_repo.find_by_id(user_id)
        return render_template(
            "user/profile.html",
            user=user,
            profile_completion=_profile_completion(user),
        ), 422


@user_bp.route("/profile/password", methods=["POST"])
@login_required
@customer_only
def change_password():
    """Ganti password pelanggan (Bab 14.2)."""
    user_id = ObjectId(session["user_id"])
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    try:
        if confirm_password is not None and confirm_password != new_password:
            raise ValidationError("Konfirmasi password tidak sama.")
        auth_service.change_password(
            user_id=user_id,
            current_password=current_password,
            new_password=new_password,
        )
        flash("Password berhasil diubah. Silakan gunakan password baru untuk login berikutnya.", "success")
        return redirect(url_for("user.profile")), 302
    except AuthenticationError as e:
        flash(e.message, "error")
        user = user_repo.find_by_id(user_id)
        return render_template(
            "user/profile.html",
            user=user,
            profile_completion=_profile_completion(user),
        ), 401
    except ValidationError as e:
        flash(e.message, "error")
        user = user_repo.find_by_id(user_id)
        return render_template(
            "user/profile.html",
            user=user,
            profile_completion=_profile_completion(user),
        ), 422
