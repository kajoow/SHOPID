"""Helper keamanan: Password hashing Argon2id (Bab 16.1)."""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

# Parameter OWASP: m=64 MiB (65536 KiB), t=3, p=4
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16
)


def hash_password(password: str) -> str:
    """Hash password menggunakan algoritma Argon2id."""
    return _hasher.hash(password)


def verify_password(hash_str: str, password: str) -> bool:
    """Verifikasi plaintext password terhadap hash Argon2id."""
    try:
        return _hasher.verify(hash_str, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hash_str: str) -> bool:
    """Periksa apakah hash perlu dihitung ulang bila parameter berubah."""
    return _hasher.check_needs_rehash(hash_str)

