"""Password hashing (bcrypt), JWT access tokens and one-time reset tokens."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from airsense.app.core.config import get_settings

PASSWORD_RULE = "at least 8 characters, including a letter and a number"  # noqa: S105 - policy text
_MAX_BCRYPT_BYTES = 72


def validate_password_strength(password: str) -> str:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError(f"Password must be {PASSWORD_RULE}.")
    if len(password.encode()) > _MAX_BCRYPT_BYTES:
        raise ValueError("Password must be at most 72 bytes.")
    return password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:_MAX_BCRYPT_BYTES], hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> tuple[str, datetime]:
    s = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=expires_minutes or s.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": exp, "iat": datetime.now(UTC), "typ": "access"}
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm), exp


def decode_access_token(token: str) -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.secret_key, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub"]})
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_reset_token() -> tuple[str, str]:
    """Returns (plain token for the user, sha256 hash stored in the DB)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
