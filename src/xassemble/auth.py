from __future__ import annotations

from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .database import Database

SESSION_COOKIE = "xassemble_session"
DEFAULT_SESSION_SECONDS = 8 * 60 * 60
MINIMUM_PASSWORD_LENGTH = 12

_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash("not-a-real-user-password")


class SessionManager:
    def __init__(self, secret_key: str, max_age: int = DEFAULT_SESSION_SECONDS):
        if len(secret_key) < 32:
            raise ValueError("XASSEMBLE_SECRET_KEY must contain at least 32 characters")
        if max_age <= 0:
            raise ValueError("Session lifetime must be positive")
        self.serializer = URLSafeTimedSerializer(secret_key, salt="xassemble-session-v1")
        self.max_age = max_age

    def create(self, user_id: int, session_version: int) -> str:
        return self.serializer.dumps(
            {"user_id": user_id, "session_version": session_version}
        )

    def read(self, token: str) -> tuple[int, int] | None:
        try:
            value = self.serializer.loads(token, max_age=self.max_age)
            user_id = value.get("user_id") if isinstance(value, dict) else None
            session_version = value.get("session_version") if isinstance(value, dict) else None
            if type(user_id) is int and type(session_version) is int:
                return user_id, session_version
            return None
        except (BadSignature, SignatureExpired):
            return None


def hash_password(password: str) -> str:
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValueError(f"Password must contain at least {MINIMUM_PASSWORD_LENGTH} characters")
    return _password_hasher.hash(password)


def authenticate(database: Database, username: str, password: str) -> dict[str, Any] | None:
    user = database.get_user_by_username(normalize_username(username))
    password_hash = user["password_hash"] if user else _dummy_password_hash
    try:
        valid = _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        valid = False
    if not user or not valid or not user["active"]:
        return None
    if _password_hasher.check_needs_rehash(password_hash):
        database.update_user_password(
            user["username"], _password_hasher.hash(password), invalidate_sessions=False
        )
    return user


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized or len(normalized) > 80:
        raise ValueError("Username must contain between 1 and 80 characters")
    if not all(character.isalnum() or character in "._-" for character in normalized):
        raise ValueError("Username may only contain letters, digits, dots, hyphens, and underscores")
    return normalized


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "name": user["name"],
        "username": user["username"],
        "role": user["role"],
        "active": bool(user["active"]),
        "must_change_password": bool(user["must_change_password"]),
    }
