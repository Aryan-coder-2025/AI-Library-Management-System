from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import clear_auth_cookies, hash_password, set_auth_cookies, verify_password
from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user
from app.models import User
from app.schemas import ChangePasswordRequest, LoginRequest, MessageResponse, PatronProfileUpdate, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=UserResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticates a user with email and password.
    Returns safe generic error messages to prevent email enumeration.
    Sets secure HttpOnly session cookie and double-submit CSRF cookie.
    Never returns password hashes or tokens in the response body.
    """
    # 1. Query user by email (case-insensitive)
    user = db.execute(
        select(User).where(User.email == credentials.email.lower().strip())
    ).scalar_one_or_none()

    # 2. Verify credentials and account status
    # Returns identical generic HTTP 401 response whether unknown email, wrong password,
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


@router.patch("/me", response_model=UserResponse, summary="Update patron profile (full_name)")
def update_profile(
    profile_in: PatronProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Updates the authenticated user's mutable profile details (full_name).
    Email, role, account status, and ID are strictly immutable through self-service.
    """
    current_user.full_name = profile_in.full_name
    db.add(current_user)
    db.commit()
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
    Rejects password reuse. Hashes the new password with bcrypt rounds=12.
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
