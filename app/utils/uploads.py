"""Helper upload file aman menggunakan Pillow dan UUID (Bab 16.1 & TC-SC-05)."""
import os
import uuid
from PIL import Image
from werkzeug.datastructures import FileStorage
from flask import current_app
from .validators import ValidationError

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}


def save_upload_image(file_storage: FileStorage, subfolder: str = "products") -> str:
    """Validasi dan simpan file gambar dengan verifikasi Pillow dan nama UUID acak."""
    if not file_storage or not file_storage.filename:
        raise ValidationError("Berkas gambar tidak ditemukan", code=422)

    # 1. Cek ekstensi file dasar
    _, ext = os.path.splitext(file_storage.filename)
    ext_lower = ext.lower()
    if ext_lower not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Hanya format JPG dan PNG yang diizinkan", code=422)

    # 2. Cek ukuran file (Maks 2 MB)
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 2 * 1024 * 1024)
    if size > max_bytes:
        raise ValidationError("Ukuran file melebihi batas maksimum 2 MB", code=422)

    # 3. Decode ulang menggunakan Pillow untuk mencegah embedded malicious code (Bab 16.1)
    try:
        img = Image.open(file_storage.stream)
        img.verify()  # Verifikasi integritas header & konten
        if img.format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError("Format gambar tidak valid", code=422)
    except Exception:
        raise ValidationError("Berkas bukan gambar yang valid atau rusak", code=422)

    # Re-open stream setelah verify() menutup pointer
    file_storage.seek(0)
    img = Image.open(file_storage.stream)

    # 4. Generate nama file unik acak (UUID v4) untuk mencegah path traversal (TC-SC-05)
    file_uuid = uuid.uuid4().hex
    target_ext = ".jpg" if img.format == "JPEG" else ".png"
    safe_filename = f"{file_uuid}{target_ext}"

    # Folder tujuan
    upload_base = os.path.abspath(current_app.config.get("UPLOAD_DIR", "instance/uploads"))
    target_dir = os.path.join(upload_base, subfolder)
    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, safe_filename)

    # Simpan gambar yang didecode ulang
    if img.format == "JPEG":
        img.convert("RGB").save(target_path, "JPEG", quality=85)
    else:
        img.save(target_path, "PNG")

    # Kembalikan URL publik / internal
    return f"/uploads/{subfolder}/{safe_filename}"

