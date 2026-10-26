from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import clear_auth_cookies, set_auth_cookies, verify_password
from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User
from app.schemas import LoginRequest, MessageResponse, UserResponse

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
