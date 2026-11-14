import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import bcrypt
from fastapi import Response
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

COOKIE_NAME = "access_token"
CSRF_COOKIE_NAME = "csrf_token"

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9._-]+$")


def validate_username(username: str) -> str:
    """
    Validates and normalizes username according to Athenaeum policy:
    - 3 to 20 characters
    - Lowercase letters, numbers, periods (.), underscores (_), and hyphens (-)
    - Rejects whitespace and unsupported characters
    - Returns normalized lowercase string
    """
    if not username:
        raise ValueError("Username cannot be empty.")
    cleaned = username.strip().lower()
    if len(cleaned) < 3 or len(cleaned) > 20:
        raise ValueError("Username must be between 3 and 20 characters long.")
    if not USERNAME_REGEX.match(cleaned):
        raise ValueError(
            "Username may only contain letters, numbers, periods (.), underscores (_), and hyphens (-)."
        )
    return cleaned


def validate_password_policy(password: str) -> str:
    """Centralized password policy: minimum 12 characters."""
    if not password or len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")
    return password


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt (max 72 bytes)."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def hash_reset_token(raw_token: str) -> str:
    """Hashes a raw password reset token using SHA-256 for secure database storage."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def generate_password_reset_token() -> Tuple[str, str]:
    """
    Generates a cryptographically secure random token (256-bit entropy via secrets)
    and its SHA-256 hash. Returns (raw_token, token_hash).
    The raw token is dispatched to the user; only token_hash is stored in the database.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    return raw_token, token_hash


# Server instance boot epoch: regenerated every time backend process starts up.
# Guarantees that when the application is stopped and restarted,
# previous session cookies are revoked, taking patrons cleanly to the login screen.
SERVER_BOOT_EPOCH: str = secrets.token_hex(16)


def create_access_token(
    user_id: int,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Creates a signed JWT access token containing subject (user_id), role, and expiration."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "epoch": SERVER_BOOT_EPOCH,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT access token, enforcing the type: 'access' claim and boot epoch."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    token_type = payload.get("type")
    if not isinstance(token_type, str) or token_type != "access":
        raise JWTError("Invalid token type; expected 'access'.")

    # Invalidate token if issued by a previous server run
    token_epoch = payload.get("epoch")
    if token_epoch is not None and token_epoch != SERVER_BOOT_EPOCH:
        raise ExpiredSignatureError("Session expired due to application restart.")

    return payload


def set_auth_cookies(response: Response, user_id: int, role: str, is_public_device: bool = False) -> str:
    """
    Sets the secure HttpOnly access_token cookie and the non-HttpOnly csrf_token cookie.
    When is_public_device is True (shared library kiosks / lab computers), max_age and expires
    are omitted so the browser retains cookies only for the duration of the browser session.
    Returns the generated csrf_token.
    """
    token = create_access_token(user_id=user_id, role=role)
    csrf_token = secrets.token_urlsafe(32)
    cookie_max_age = None if is_public_device else (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    cookie_expires = None if is_public_device else cookie_max_age

    # 1. HttpOnly access_token cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=cookie_max_age,
        expires=cookie_expires,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        domain=settings.COOKIE_DOMAIN or None,
        path="/",
    )

    # 2. Non-HttpOnly csrf_token cookie for double-submit verification
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        max_age=cookie_max_age,
        expires=cookie_expires,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        domain=settings.COOKIE_DOMAIN or None,
        path="/",
    )

    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    """Deletes both access_token and csrf_token cookies."""
    response.delete_cookie(
        key=COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN or None,
        path="/",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN or None,
        path="/",
    )
