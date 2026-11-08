from datetime import datetime, timedelta
import logging
import time
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    clear_auth_cookies,
    generate_password_reset_token,
    hash_password,
    hash_reset_token,
    set_auth_cookies,
    verify_password,
)
from app.config import get_settings
from app.database import atomic_write, get_db, get_write_db
from app.dependencies import get_current_active_user
from app.models import PasswordResetToken, User
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    PatronProfileUpdate,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.email import email_service

logger = logging.getLogger("athenaeum.auth")
settings = get_settings()

_forgot_password_attempts: Dict[str, List[float]] = {}
FORGOT_PASSWORD_WINDOW_SECONDS = 900.0  # 15 minutes
FORGOT_PASSWORD_MAX_ATTEMPTS = 5


def check_forgot_password_rate_limit(key: str) -> bool:
    """In-memory rate limiter per client IP. Window: 15m, Max: 5 attempts."""
    now = time.time()
    attempts = _forgot_password_attempts.get(key, [])
    valid_attempts = [t for t in attempts if now - t < FORGOT_PASSWORD_WINDOW_SECONDS]
    if len(valid_attempts) >= FORGOT_PASSWORD_MAX_ATTEMPTS:
        _forgot_password_attempts[key] = valid_attempts
        return False
    valid_attempts.append(now)
    _forgot_password_attempts[key] = valid_attempts
    return True


def reset_forgot_password_rate_limit() -> None:
    """Helper for test cleanup."""
    _forgot_password_attempts.clear()


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=UserResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticates a user with email address OR username and password.
    Returns safe generic error messages to prevent account enumeration.
    Sets secure HttpOnly session cookie and double-submit CSRF cookie.
    Never returns password hashes or tokens in the response body.
    """
    # 1. Query user by email OR username (case-insensitive)
    clean_id = (credentials.identifier or credentials.email or credentials.username or "").strip().lower()

    user = db.execute(
        select(User).where(
            or_(
                func.lower(User.email) == clean_id,
                func.lower(User.username) == clean_id,
            )
        )
    ).scalar_one_or_none()

    # 2. Verify credentials and account status
    # Returns identical generic HTTP 401 response whether unknown email/username, wrong password,
    # or inactive account to prevent account existence enumeration attacks.
    is_password_valid = verify_password(credentials.password, user.hashed_password) if user else False

    if not user or not is_password_valid or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # 4. Set secure session cookies (HttpOnly access_token + non-HttpOnly csrf_token)
    set_auth_cookies(response, user_id=user.id, role=user.role)

    # 5. Return user profile without password or token
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Public student registration")
def register(
    reg_in: RegisterRequest,
    response: Response,
    db: Session = Depends(get_write_db),
):
    """
    Registers a new student account.
    - Public registration strictly provisions student role accounts only.
    - Never permits role selection or privilege escalation.
    - Enforces unique email and unique username (case-insensitive).
    - Enforces 12-character minimum password policy.
    - Sets secure session cookies upon successful registration.
    """
    clean_email = reg_in.email.strip().lower()
    clean_username = reg_in.username.strip().lower()
    clean_name = reg_in.full_name.strip()

    with atomic_write(db):
        # 1. Check email uniqueness
        existing_email = db.execute(
            select(User).where(func.lower(User.email) == clean_email)
        ).scalar_one_or_none()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists.",
            )

        # 2. Check username uniqueness
        existing_uname = db.execute(
            select(User).where(func.lower(User.username) == clean_username)
        ).scalar_one_or_none()
        if existing_uname:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This username is already taken. Please choose another.",
            )

        # 3. Create student record
        new_user = User(
            email=clean_email,
            username=clean_username,
            full_name=clean_name,
            hashed_password=hash_password(reg_in.password),
            role="student",  # Hardcoded student role: never allows user-supplied role
            is_active=True,
        )
        db.add(new_user)
        try:
            db.flush()
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email or username already exists.",
            )

        # Issue secure auth cookies so patron is immediately logged in
        set_auth_cookies(response, user_id=new_user.id, role=new_user.role)
        return new_user


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    """
    Logs out the current user by clearing authentication and CSRF cookies.
    """
    clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns the authenticated user's profile.
    Requires an active authenticated session.
    """
    return current_user


@router.patch("/me", response_model=UserResponse, summary="Update patron profile (full_name, username)")
def update_profile(
    profile_in: PatronProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Updates the authenticated user's mutable profile details (full_name and/or username).
    Email, role, account status, and ID are strictly immutable through self-service.
    """
    with atomic_write(db):
        if profile_in.full_name is not None:
            current_user.full_name = profile_in.full_name

        if profile_in.username is not None:
            clean_username = profile_in.username.strip().lower()
            if clean_username != (current_user.username or "").lower():
                existing = db.execute(
                    select(User).where(
                        func.lower(User.username) == clean_username,
                        User.id != current_user.id,
                    )
                ).scalar_one_or_none()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This username is already taken. Please choose another.",
                    )
                current_user.username = clean_username

        db.add(current_user)
        db.flush()
        db.refresh(current_user)
        return current_user


@router.post("/change-password", response_model=MessageResponse, summary="Change patron password")
def change_password(
    pwd_in: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Changes the authenticated user's password after verifying the current password.
    Rejects password reuse. Hashes the new password with bcrypt rounds=12 (min 12 characters).
    Clears authentication cookies upon success to require re-authentication.
    """
    if not verify_password(pwd_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )

    if pwd_in.new_password == pwd_in.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot match the existing password.",
        )

    current_user.hashed_password = hash_password(pwd_in.new_password)
    db.add(current_user)
    db.commit()

    # Clear authentication cookies so the user is required to re-authenticate with the new credentials
    clear_auth_cookies(response)

    return MessageResponse(message="Password changed successfully. Please log in again with your new password.")


@router.post("/forgot-password", response_model=MessageResponse, summary="Request password reset link")
def forgot_password(
    request: Request,
    req_in: ForgotPasswordRequest,
    db: Session = Depends(get_write_db),
):
    """
    Submits a password-reset request.
    - Uniform response regardless of whether account exists to prevent email enumeration.
    - In-memory rate limiting applied per IP.
    - Generates cryptographically secure token (secrets module).
    - Persists only SHA-256 hash of the token.
    - Invalidates previously issued active reset tokens for this user.
    - Dispatches branded email via configured SMTP service.
    """
    # 1. Rate limiting check
    client_ip = request.client.host if request.client else "unknown"
    if not check_forgot_password_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please wait a few minutes before trying again.",
        )

    clean_email = req_in.email.strip().lower()

    # 2. Look up user
    user = db.execute(
        select(User).where(func.lower(User.email) == clean_email)
    ).scalar_one_or_none()

    # 3. If user exists and is active, issue token and send email
    if user and user.is_active:
        raw_token, token_hash = generate_password_reset_token()
        now = datetime.utcnow()
        expire_time = now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)

        try:
            with atomic_write(db):
                # Invalidate existing active tokens for this user
                db.execute(
                    update(PasswordResetToken)
                    .where(
                        PasswordResetToken.user_id == user.id,
                        PasswordResetToken.is_used == False,
                    )
                    .values(is_used=True, used_at=now)
                )

                # Persist new token record
                new_token_record = PasswordResetToken(
                    user_id=user.id,
                    token_hash=token_hash,
                    created_at=now,
                    expires_at=expire_time,
                    is_used=False,
                )
                db.add(new_token_record)

            # Send email
            sent = email_service.send_password_reset_email(
                to_email=user.email,
                recipient_name=user.full_name,
                reset_token=raw_token,
            )
            if not sent and settings.EMAIL_ENABLED:
                logger.error("Failed to dispatch password recovery email for user_id=%s", user.id)
        except Exception as exc:
            logger.error("Error creating password reset record for user_id=%s: %s", user.id, type(exc).__name__)

    # 4. Generic response to prevent account enumeration
    return MessageResponse(
        message="If an account with that email exists, password reset instructions have been sent."
    )


@router.post("/reset-password", response_model=MessageResponse, summary="Reset password using reset token")
def reset_password(
    req_in: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_write_db),
):
    """
    Consumes a secure reset token and updates the user's password.
    - Validates token existence, expiration, and single-use status.
    - Enforces 12-character minimum password policy.
    - Atomically updates password hash, marks token used, and invalidates other tokens.
    - Clears existing authentication cookies to invalidate the current browser session.
    """
    token_hash = hash_reset_token(req_in.token)

    # 1. Look up token by hash
    token_record = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    # 2. Check if already used
    if token_record.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset token has already been used.",
        )

    # 3. Check expiration
    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset token has expired. Please request a new one.",
        )

    # 4. Fetch associated user
    user = db.execute(
        select(User).where(User.id == token_record.user_id)
    ).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    # 5. Atomically update password and consume token
    now = datetime.utcnow()
    with atomic_write(db):
        user.hashed_password = hash_password(req_in.new_password)
        token_record.is_used = True
        token_record.used_at = now
        db.add(user)
        db.add(token_record)

        # Invalidate any other outstanding active tokens for this user
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != token_record.id,
                PasswordResetToken.is_used == False,
            )
            .values(is_used=True, used_at=now)
        )

    # Clear auth cookies
    clear_auth_cookies(response)

    return MessageResponse(
        message="Your password has been successfully reset. Please log in with your new password."
    )
