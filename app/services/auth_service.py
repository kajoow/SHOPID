"""Auth service: Logika bisnis autentikasi, registrasi, dan profil (Bab 7.A, 14.2)."""
from bson import ObjectId
from ..repositories import user_repo, audit_repo
from ..utils.security import hash_password, verify_password, needs_rehash
from ..utils.validators import (
    validate_email,
    validate_password,
    validate_string,
    validate_phone,
    ValidationError,
)
from ..models.enums import UserRole


class AuthenticationError(Exception):
    def __init__(self, message: str = "Email atau password salah", code: int = 401):
        super().__init__(message)
        self.message = message
        self.code = code


class ConflictError(Exception):
    def __init__(self, message: str = "Data sudah ada", code: int = 409):
        super().__init__(message)
        self.message = message
        self.code = code


class AuthService:
    def register_user(
        self,
        name: str,
        email: str,
        password: str,
        phone: str | None = None,
    ) -> ObjectId:
        """Registrasi akun pelanggan baru. Role selalu dipaksa 'user' (Bab 7.A)."""
        valid_name = validate_string(name, min_len=2, max_len=100, field_name="Nama lengkap")
        valid_email = validate_email(email)
        valid_password = validate_password(password)
        valid_phone = validate_phone(phone)

        # Cek duplikasi email (case-insensitive)
        existing = user_repo.find_by_email(valid_email)
        if existing:
            raise ConflictError(f"Email '{valid_email}' sudah terdaftar.")

        pwd_hash = hash_password(valid_password)

        user_id = user_repo.insert(
            name=valid_name,
            email=valid_email,
            password_hash=pwd_hash,
            role=UserRole.USER,  # Selalu user, input role diabaikan
            phone=valid_phone,
            address=None,
            is_active=True,
        )

        return user_id

    def authenticate_user(self, email_input: str, password_input: str) -> dict:
        """Autentikasi login dengan verifikasi Argon2id dan pesan error generik (Bab 7.A)."""
        # Pesan generik yang sama agar tidak membocorkan keberadaan akun (TC-AU-07)
        generic_err = "Email atau password salah"

        if not email_input or not isinstance(email_input, str):
            raise AuthenticationError(generic_err)
        if not password_input or not isinstance(password_input, str):
            raise AuthenticationError(generic_err)

        email = email_input.strip().lower()
        user = user_repo.find_by_email(email)
        if not user:
            raise AuthenticationError(generic_err)

        if not user.get("is_active", True):
            raise AuthenticationError("Akun dinonaktifkan. Silakan hubungi admin.", code=403)

        if not verify_password(user.get("password_hash", ""), password_input):
            raise AuthenticationError(generic_err)

        # Rehash jika parameter keamanan berubah
        if needs_rehash(user["password_hash"]):
            new_hash = hash_password(password_input)
            user_repo.update_password(user["_id"], new_hash)

        # Return user tanpa field password_hash (TC-SC-09)
        safe_user = dict(user)
        safe_user.pop("password_hash", None)
        return safe_user

    def update_profile(
        self,
        user_id: ObjectId,
        name: str | None = None,
        phone: str | None = None,
        address: str | None = None,
    ) -> dict:
        """Mengubah profil data diri. Email dan role tidak dapat diubah (Bab 14.2)."""
        updates = {}
        if name is not None:
            updates["name"] = validate_string(name, min_len=2, max_len=100, field_name="Nama")
        if phone is not None:
            updates["phone"] = validate_phone(phone)
        if address is not None:
            if address == "":
                updates["address"] = None
            else:
                updates["address"] = validate_string(address, min_len=1, max_len=300, field_name="Alamat")

        if updates:
            user_repo.update_profile(user_id, updates)

        user = user_repo.find_by_id(user_id)
        if not user:
            raise ValidationError("Pengguna tidak ditemukan", code=404)

        safe_user = dict(user)
        safe_user.pop("password_hash", None)
        return safe_user

    def change_password(self, user_id: ObjectId, current_password: str, new_password: str) -> bool:
        """Ganti password dengan validasi password lama dan kekuatan password baru."""
        user = user_repo.find_by_id(user_id)
        if not user:
            raise ValidationError("Pengguna tidak ditemukan", code=404)

        if not verify_password(user.get("password_hash", ""), current_password):
            raise AuthenticationError("Password lama salah", code=401)

        valid_new_pwd = validate_password(new_password)
        new_hash = hash_password(valid_new_pwd)

        user_repo.update_password(user_id, new_hash)

        audit_repo.log(
            actor_id=user_id,
            action="user.password_change",
            entity_type="users",
            entity_id=user_id,
        )
        return True


auth_service = AuthService()

