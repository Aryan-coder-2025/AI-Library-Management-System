import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
from fastapi import Response
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

COOKIE_NAME = "access_token"
CSRF_COOKIE_NAME = "csrf_token"


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
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT access token."""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def set_auth_cookies(response: Response, user_id: int, role: str) -> str:
    """
    Sets the secure HttpOnly access_token cookie and the non-HttpOnly csrf_token cookie.
    Returns the generated csrf_token.
    """
    token = create_access_token(user_id=user_id, role=role)
    csrf_token = secrets.token_urlsafe(32)
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    # 1. HttpOnly access_token cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=max_age,
        expires=max_age,
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
        max_age=max_age,
        expires=max_age,
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
