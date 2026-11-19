"""Validator pusat untuk sanitasi dan validasi tipe ketat (Bab 16.1).
Mencegah NoSQL injection dengan memastikan seluruh input berupa tipe skalar eksplisit.
"""
import re
import unicodedata
from bson import ObjectId
from bson.errors import InvalidId


class ValidationError(Exception):
    def __init__(self, message: str, field: str | None = None, code: int = 422):
        super().__init__(message)
        self.message = message
        self.field = field
        self.code = code


def sanitize_string(val: any) -> str:
    """Trim spasi, normalisasi Unicode NFC, buang karakter kontrol."""
    if not isinstance(val, str):
        raise ValidationError("Input harus bertipe string", code=400)
    # Normalisasi Unicode
    norm = unicodedata.normalize("NFC", val.strip())
    # Buang karakter kontrol non-printable (kecuali newline dan tab)
    return "".join(ch for ch in norm if unicodedata.category(ch)[0] != "C" or ch in "\n\t\r")


def validate_string(val: any, min_len: int = 1, max_len: int = 1000, field_name: str = "Field") -> str:
    if val is None or not isinstance(val, str):
        raise ValidationError(f"{field_name} wajib bertipe string", field=field_name, code=400)
    s = sanitize_string(val)
    if len(s) < min_len:
        raise ValidationError(f"{field_name} minimal {min_len} karakter", field=field_name, code=422)
    if max_len and len(s) > max_len:
        raise ValidationError(f"{field_name} maksimal {max_len} karakter", field=field_name, code=422)
    return s


def validate_email(email_input: any) -> str:
    if email_input is None or not isinstance(email_input, str):
        raise ValidationError("Email harus berupa teks", field="email", code=400)
    email = sanitize_string(email_input).lower()
    if len(email) > 254:
        raise ValidationError("Email maksimal 254 karakter", field="email", code=422)
    # Validasi format email RFC 5322 sederhana
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, email):
        raise ValidationError("Format email tidak valid", field="email", code=422)
    return email


def validate_password(password_input: any) -> str:
    if password_input is None or not isinstance(password_input, str):
        raise ValidationError("Password harus berupa teks", field="password", code=400)
    # Password tidak di-trim agar spasi intentional user tetap terjaga
    if len(password_input) < 8:
        raise ValidationError("Password minimal 8 karakter", field="password", code=422)
    # Harus memuat huruf dan angka
    has_letter = any(c.isalpha() for c in password_input)
    has_digit = any(c.isdigit() for c in password_input)
    if not (has_letter and has_digit):
        raise ValidationError("Password harus mengandung huruf dan angka", field="password", code=422)
    return password_input


def validate_phone(phone_input: any) -> str | None:
    if phone_input is None or phone_input == "":
        return None
    if not isinstance(phone_input, str):
        raise ValidationError("Nomor telepon harus berupa teks", field="phone", code=400)
    phone = sanitize_string(phone_input)
    # Format Indonesia: ^(\+62|62|0)8[1-9][0-9]{7,11}$
    pattern = r"^(\+62|62|0)8[1-9][0-9]{7,11}$"
    if not re.match(pattern, phone):
        raise ValidationError("Format nomor telepon Indonesia tidak valid", field="phone", code=422)
    return phone


def validate_int(val: any, min_val: int | None = None, max_val: int | None = None, field_name: str = "Angka") -> int:
    if isinstance(val, bool) or val is None:
        raise ValidationError(f"{field_name} harus berupa integer", field=field_name, code=400)
    try:
        n = int(val)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} harus berupa integer", field=field_name, code=400)

    if min_val is not None and n < min_val:
        raise ValidationError(f"{field_name} minimal {min_val}", field=field_name, code=422)
    if max_val is not None and n > max_val:
        raise ValidationError(f"{field_name} maksimal {max_val}", field=field_name, code=422)
    return n


def validate_object_id(oid: any, field_name: str = "ID") -> ObjectId:
    if isinstance(oid, ObjectId):
        return oid
    if not isinstance(oid, str):
        raise ValidationError(f"{field_name} tidak valid", field=field_name, code=400)
    try:
        return ObjectId(oid)
    except InvalidId:
        raise ValidationError(f"{field_name} tidak valid", field=field_name, code=404)


def validate_enum(val: any, allowed_list: list, field_name: str = "Pilihan") -> str:
    if val not in allowed_list:
        raise ValidationError(f"{field_name} tidak valid. Pilihan yang diizinkan: {allowed_list}", field=field_name, code=422)
    return val

