from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Turn a password into a hash that is safe to store."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True only if the password matches the stored hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False