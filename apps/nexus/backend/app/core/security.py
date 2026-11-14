"""Password hashing, session tokens, CSRF and encryption of stored secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_BYTES = 72


def hash_password(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    raw = password.encode("utf-8")
    if len(raw) > PASSWORD_MAX_BYTES:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        raw = password.encode("utf-8")
        if len(raw) > PASSWORD_MAX_BYTES:
            return False
        return bcrypt.checkpw(raw, password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def new_token(byte_length: int = 32) -> str:
    return secrets.token_urlsafe(byte_length)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"nexus-config-secrets:{settings.secret_key}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str | None:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def mask_credential(value: str | None) -> str:
    if not value:
        return "—"
    if len(value) <= 6:
        return "•••"
    return f"{value[:4]}…{value[-2:]}"
