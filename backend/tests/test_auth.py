from datetime import timedelta
import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.cli import create_librarian_account
from app.database import atomic_write, get_db
from app.dependencies import require_librarian, require_student
from app.main import app
from app.models import User

# Test router to test role-based access control dependencies
access_test_router = APIRouter(prefix="/api/test-access", tags=["Test"])


@access_test_router.get("/librarian-only")
def librarian_endpoint(user: User = Depends(require_librarian)):
    return {"message": "Welcome librarian", "user_id": user.id}


@access_test_router.get("/student-only")
def student_endpoint(user: User = Depends(require_student)):
    return {"message": "Welcome student", "user_id": user.id}


app.include_router(access_test_router)


@pytest.fixture
def test_users(db: Session):
    """Creates a student and a librarian user for testing."""
    with atomic_write(db):
        librarian = User(
            email="head_librarian@library.org",
            full_name="Head Librarian",
            hashed_password=hash_password("LibrarianPass123!"),
            role="librarian",
            is_active=True,
        )
        student = User(
            email="active_student@university.edu",
            full_name="Active Student",
            hashed_password=hash_password("StudentPass123!"),
            role="student",
            is_active=True,
        )
        inactive = User(
            email="inactive_user@university.edu",
            full_name="Inactive User",
            hashed_password=hash_password("InactivePass123!"),
            role="student",
            is_active=False,
        )
        db.add_all([librarian, student, inactive])
        db.flush()

        data = {
            "librarian_id": librarian.id,
            "student_id": student.id,
            "inactive_id": inactive.id,
        }
    return data


# ── 1. Authentication APIs ───────────────────────────────────────────────────

def test_login_success_sets_cookies(client, test_users):
    """
    Verifies that a valid login:
    - Returns 200 with user profile.
    - Does NOT return password hash or JWT token in response body.
    - Sets HttpOnly access_token cookie and non-HttpOnly csrf_token cookie.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "head_librarian@library.org", "password": "LibrarianPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "head_librarian@library.org"
    assert data["full_name"] == "Head Librarian"
    assert data["role"] == "librarian"
    assert "password" not in data
    assert "hashed_password" not in data
    assert "access_token" not in data
    assert "token" not in data

    # Verify cookies
    assert "access_token" in response.cookies
    assert "csrf_token" in response.cookies


def test_login_invalid_password_returns_generic_error(client, test_users):
    """
    Verifies that an incorrect password returns 401 with a generic error
    and does not set authentication cookies.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "head_librarian@library.org", "password": "WrongPassword999"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert "access_token" not in response.cookies
    assert "csrf_token" not in response.cookies


def test_login_nonexistent_email_returns_identical_generic_error(client, test_users):
    """
    Verifies that non-existent email returns the exact same 401 error,
    preventing user enumeration attacks.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@nowhere.com", "password": "SomePassword123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert "access_token" not in response.cookies
    assert "csrf_token" not in response.cookies


def test_login_inactive_user_rejected(client, test_users):
    """
    Verifies that inactive user accounts cannot log in even with valid credentials,
    and receive the exact same 401 error and no cookies as unknown/wrong password cases.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "inactive_user@university.edu", "password": "InactivePass123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert "access_token" not in response.cookies
    assert "csrf_token" not in response.cookies


@pytest.mark.parametrize(
    "email,password",
    [
        ("head_librarian@library.org", "WrongPassword999"),
        ("nonexistent_user@library.org", "AnyPassword123!"),
        ("inactive_user@university.edu", "InactivePass123!"),
        ("inactive_user@university.edu", "WrongPassword999"),
    ],
)
def test_all_failed_logins_return_identical_status_and_message(client, test_users, email, password):
    """
    Verifies that all failed login attempts (unknown email, wrong password, inactive user)
    return the exact same HTTP 401 status code and 'Invalid email or password.' message,
    and never set authentication cookies.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}
    assert "access_token" not in response.cookies
    assert "csrf_token" not in response.cookies


def test_login_disallowed_origin_rejected(client, test_users):
    """
    Verifies that login requests from unauthorized origins are rejected with 403
    by the SecurityMiddleware Origin check.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "head_librarian@library.org", "password": "LibrarianPass123!"},
        headers={"Origin": "http://evil-attacker.com"},
    )
    assert response.status_code == 403
    assert "not permitted" in response.json()["detail"]


# ── 2. Current User / Session Endpoint ───────────────────────────────────────

def test_get_current_user_profile(client, test_users):
    """
    Verifies /api/auth/me returns the profile for a logged-in user.
    """
    # Log in first
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "active_student@university.edu", "password": "StudentPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert login_resp.status_code == 200

    # Call /api/auth/me using the session cookies
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["email"] == "active_student@university.edu"
    assert data["role"] == "student"
    assert "hashed_password" not in data


def test_get_current_user_unauthenticated(client):
    """
    Verifies /api/auth/me returns 401 when no session cookie or header is sent.
    """
    client.cookies.clear()
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


def test_get_current_user_expired_token(client, test_users):
    """
    Verifies that an expired JWT token returns 401 with session expired detail.
    """
    # Create an expired token (-1 hour)
    expired_token = create_access_token(
        user_id=test_users["student_id"],
        role="student",
        expires_delta=timedelta(hours=-1),
    )
    client.cookies.set("access_token", expired_token)

    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Session has expired" in response.json()["detail"]


def test_get_current_user_tampered_token(client):
    """
    Verifies that a forged/tampered token returns 401.
    """
    client.cookies.set("access_token", "invalid.jwt.signature")
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


def test_logout_clears_cookies(client, test_users):
    """
    Verifies that /api/auth/logout clears auth cookies and subsequent requests are unauthenticated.
    """
    # 1. Log in
    client.post(
        "/api/auth/login",
        json={"email": "head_librarian@library.org", "password": "LibrarianPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )

    # 2. Call /api/auth/logout
    logout_resp = client.post(
        "/api/auth/logout",
        headers={"Origin": "http://localhost:5173"},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Logged out successfully."

    # 3. Subsequent /api/auth/me must fail with 401
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401


# ── 3. Role-Based Authorization ──────────────────────────────────────────────

def test_librarian_can_access_librarian_endpoint(client, test_users):
    """
    Verifies librarian user can access librarian-only endpoints.
    """
    client.post(
        "/api/auth/login",
        json={"email": "head_librarian@library.org", "password": "LibrarianPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    response = client.get("/api/test-access/librarian-only")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome librarian"


def test_student_forbidden_from_librarian_endpoint(client, test_users):
    """
    Verifies student user receives 403 Forbidden when attempting to access librarian endpoints.
    """
    client.post(
        "/api/auth/login",
        json={"email": "active_student@university.edu", "password": "StudentPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    response = client.get("/api/test-access/librarian-only")
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


def test_librarian_forbidden_from_student_endpoint(client, test_users):
    """
    Verifies librarian user receives 403 Forbidden when attempting to access student-only endpoints.
    """
    client.post(
        "/api/auth/login",
        json={"email": "head_librarian@library.org", "password": "LibrarianPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    response = client.get("/api/test-access/student-only")
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


def test_inactive_account_with_valid_jwt_blocked_from_endpoints(client, test_users):
    """
    Verifies that if an inactive user possesses a valid JWT token,
    all authenticated endpoints reject the request with HTTP 401 'Account is inactive.'
    """
    token = create_access_token(user_id=test_users["inactive_id"], role="student")
    client.cookies.set("access_token", token)

    # 1. /api/auth/me rejects inactive account
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401
    assert me_resp.json()["detail"] == "Account is inactive."

    # 2. Role-protected endpoint rejects inactive account
    role_resp = client.get("/api/test-access/student-only")
    assert role_resp.status_code == 401
    assert role_resp.json()["detail"] == "Account is inactive."


def test_deactivating_account_in_database_immediately_revokes_access(client, test_users, db: Session):
    """
    Verifies that deactivating an account directly in the database immediately blocks
    any existing active sessions on their next request.
    """
    # 1. Active student logs in successfully
    client.post(
        "/api/auth/login",
        json={"email": "active_student@university.edu", "password": "StudentPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200

    # 2. Deactivate the student account directly in the database
    student = db.get(User, test_users["student_id"])
    student.is_active = False
    db.flush()

    # 3. Subsequent requests with existing cookie session are immediately rejected with 401
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401
    assert me_resp.json()["detail"] == "Account is inactive."

    student_ep_resp = client.get("/api/test-access/student-only")
    assert student_ep_resp.status_code == 401
    assert student_ep_resp.json()["detail"] == "Account is inactive."


def test_role_change_in_database_immediately_updates_permissions(client, test_users, db: Session):
    """
    Verifies that updating a user's role directly in the database takes effect immediately
    for subsequent requests, ensuring authorization checks verify against the database.
    """
    # 1. Log in as student
    client.post(
        "/api/auth/login",
        json={"email": "active_student@university.edu", "password": "StudentPass123!"},
        headers={"Origin": "http://localhost:5173"},
    )

    # Student can access student endpoint, but not librarian endpoint
    assert client.get("/api/test-access/student-only").status_code == 200
    assert client.get("/api/test-access/librarian-only").status_code == 403

    # 2. Promote student to librarian in database
    user = db.get(User, test_users["student_id"])
    user.role = "librarian"
    db.flush()

    # Now the same session immediately has librarian access and loses student-only access
    assert client.get("/api/test-access/librarian-only").status_code == 200
    assert client.get("/api/test-access/student-only").status_code == 403

    # 3. Demote back to student in database
    user = db.get(User, test_users["student_id"])
    user.role = "student"
    db.flush()

    # Immediately reflected: librarian-only becomes 403 again
    assert client.get("/api/test-access/librarian-only").status_code == 403
    assert client.get("/api/test-access/student-only").status_code == 200


# ── 4. Librarian Bootstrap CLI ───────────────────────────────────────────────

def test_cli_bootstrap_librarian_success(db):
    """
    Verifies the bootstrap CLI helper creates a librarian with hashed password
    and correct role.
    """
    librarian = create_librarian_account(
        email="cli_librarian@library.org",
        full_name="CLI Librarian",
        password="SecureBootstrapPassword123!",
        initial_only=False,
        interactive=False,
        db_session=db,
    )
    assert librarian.id is not None
    assert librarian.email == "cli_librarian@library.org"
    assert librarian.role == "librarian"
    assert librarian.is_active is True
    assert librarian.hashed_password != "SecureBootstrapPassword123!"


def test_cli_bootstrap_rejects_duplicate_email(db):
    """
    Verifies that the bootstrap CLI rejects duplicate email addresses.
    """
    create_librarian_account(
        email="first_lib@library.org",
        full_name="First Lib",
        password="SecurePassword123!",
        initial_only=False,
        interactive=False,
        db_session=db,
    )
    with pytest.raises(ValueError, match="already exists"):
        create_librarian_account(
            email="first_lib@library.org",
            full_name="Second Lib",
            password="SecurePassword456!",
            initial_only=False,
            interactive=False,
            db_session=db,
        )


def test_cli_bootstrap_initial_only_flag(db):
    """
    Verifies that --initial-only prevents creating an additional librarian when one exists.
    """
    create_librarian_account(
        email="only_lib@library.org",
        full_name="Only Lib",
        password="SecurePassword123!",
        initial_only=False,
        interactive=False,
        db_session=db,
    )
    with pytest.raises(ValueError, match="--initial-only was specified"):
        create_librarian_account(
            email="second_lib@library.org",
            full_name="Second Lib",
            password="SecurePassword456!",
            initial_only=True,
            interactive=False,
            db_session=db,
        )


def test_cli_bootstrap_rejects_short_password(db):
    """
    Verifies that the bootstrap CLI validates password length (minimum 8 chars).
    """
    with pytest.raises(ValueError, match="at least 8 characters"):
        create_librarian_account(
            email="short_pw@library.org",
            full_name="Short PW",
            password="short",
            initial_only=False,
            interactive=False,
            db_session=db,
        )


def test_cli_parser_does_not_encourage_password_argument():
    """
    Verifies that the CLI argument parser does not expose or encourage a --password
    command-line argument, preventing secrets from leaking into process lists and shell history.
    """
    from unittest.mock import patch
    from app.cli import main

    with patch("sys.argv", ["cli.py", "--password", "InsecureCLIArg123!"]):
        with pytest.raises(SystemExit):
            main()


def test_cli_main_supports_env_var_password(db, monkeypatch):
    """
    Verifies that main() accepts the password via the LIBRARIAN_BOOTSTRAP_PASSWORD environment variable
    for secure headless automation without CLI argument exposure.
    """
    from unittest.mock import patch
    from app.cli import main

    monkeypatch.setenv("LIBRARIAN_BOOTSTRAP_PASSWORD", "EnvSecurePass123!")

    with patch("sys.argv", ["cli.py", "--email", "headless_lib@library.org", "--full-name", "Headless Lib"]):
        with patch("app.cli.init_db"):
            with patch("app.cli.SessionLocal") as mock_session_cls:
                mock_session_cls.return_value.__enter__.return_value = db
                mock_session_cls.return_value.__exit__.return_value = None
                main()

    user = db.execute(select(User).where(User.email == "headless_lib@library.org")).scalar_one_or_none()
    assert user is not None
    assert user.role == "librarian"
    assert user.full_name == "Headless Lib"


def test_cli_supplying_email_does_not_bypass_confirmation_when_librarian_exists(db, monkeypatch):
    """
    Verifies that supplying --email does NOT silently bypass confirmation when an existing
    librarian is present. If the user declines confirmation ('n'), creation is aborted.
    """
    from unittest.mock import patch
    from app.cli import main

    # 1. Existing librarian in database
    create_librarian_account(
        email="first_admin@library.org",
        full_name="First Admin",
        password="SecurePassword123!",
        confirm_additional=True,
        db_session=db,
    )

    monkeypatch.setenv("LIBRARIAN_BOOTSTRAP_PASSWORD", "AnotherSecurePass123!")

    # 2. Operator passes --email on CLI, but inputs 'n' when prompted to confirm additional librarian
    with patch("sys.argv", ["cli.py", "--email", "second_admin@library.org", "--full-name", "Second Admin"]):
        with patch("app.cli.init_db"):
            with patch("app.cli.SessionLocal") as mock_session_cls:
                mock_session_cls.return_value.__enter__.return_value = db
                mock_session_cls.return_value.__exit__.return_value = None
                with patch("builtins.input", return_value="n"):
                    with pytest.raises(SystemExit) as excinfo:
                        main()
                    assert excinfo.value.code == 1

    # 3. Ensure second librarian was NOT created
    user = db.execute(select(User).where(User.email == "second_admin@library.org")).scalar_one_or_none()
    assert user is None


def test_cli_supplying_email_creates_librarian_when_confirmed_interactively(db, monkeypatch):
    """
    Verifies that supplying --email prompts for confirmation when a librarian exists,
    and successfully creates the account when confirmed ('y').
    """
    from unittest.mock import patch
    from app.cli import main

    create_librarian_account(
        email="existing_lib@library.org",
        full_name="Existing Lib",
        password="SecurePassword123!",
        confirm_additional=True,
        db_session=db,
    )

    monkeypatch.setenv("LIBRARIAN_BOOTSTRAP_PASSWORD", "SecondPassword123!")

    with patch("sys.argv", ["cli.py", "--email", "second_confirmed@library.org", "--full-name", "Second Confirmed"]):
        with patch("app.cli.init_db"):
            with patch("app.cli.SessionLocal") as mock_session_cls:
                mock_session_cls.return_value.__enter__.return_value = db
                mock_session_cls.return_value.__exit__.return_value = None
                with patch("builtins.input", return_value="y"):
                    main()

    user = db.execute(select(User).where(User.email == "second_confirmed@library.org")).scalar_one_or_none()
    assert user is not None
    assert user.role == "librarian"


def test_cli_confirm_additional_flag_explicitly_allows_creation(db, monkeypatch):
    """
    Verifies that the --confirm-additional flag explicitly confirms creation of an additional
    librarian account without requiring an interactive prompt.
    """
    from unittest.mock import patch
    from app.cli import main

    create_librarian_account(
        email="base_lib@library.org",
        full_name="Base Lib",
        password="SecurePassword123!",
        confirm_additional=True,
        db_session=db,
    )

    monkeypatch.setenv("LIBRARIAN_BOOTSTRAP_PASSWORD", "ThirdPassword123!")

    with patch("sys.argv", [
        "cli.py",
        "--email", "flag_confirmed@library.org",
        "--full-name", "Flag Confirmed",
        "--confirm-additional",
    ]):
        with patch("app.cli.init_db"):
            with patch("app.cli.SessionLocal") as mock_session_cls:
                mock_session_cls.return_value.__enter__.return_value = db
                mock_session_cls.return_value.__exit__.return_value = None
                main()

    user = db.execute(select(User).where(User.email == "flag_confirmed@library.org")).scalar_one_or_none()
    assert user is not None
    assert user.role == "librarian"


def test_cli_non_interactive_without_confirm_additional_fails(db, monkeypatch):
    """
    Verifies that in non-interactive mode, creating an additional librarian without
    --confirm-additional fails explicitly with exit code 1.
    """
    from unittest.mock import patch
    from app.cli import main

    create_librarian_account(
        email="primary_lib@library.org",
        full_name="Primary Lib",
        password="SecurePassword123!",
        confirm_additional=True,
        db_session=db,
    )

    monkeypatch.setenv("LIBRARIAN_BOOTSTRAP_PASSWORD", "FourthPassword123!")

    with patch("sys.argv", [
        "cli.py",
        "--email", "unconfirmed_additional@library.org",
        "--full-name", "Unconfirmed Additional",
        "--non-interactive",
    ]):
        with patch("app.cli.init_db"):
            with patch("app.cli.SessionLocal") as mock_session_cls:
                mock_session_cls.return_value.__enter__.return_value = db
                mock_session_cls.return_value.__exit__.return_value = None
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 1

    user = db.execute(select(User).where(User.email == "unconfirmed_additional@library.org")).scalar_one_or_none()
    assert user is None


def test_cli_initial_only_safeguard_overrides_confirm_additional(db):
    """
    Verifies that --initial-only strictly prevents creating an additional librarian
    even if confirm_additional is passed.
    """
    create_librarian_account(
        email="first_safeguard@library.org",
        full_name="First Safeguard",
        password="SecurePassword123!",
        confirm_additional=True,
        db_session=db,
    )

    with pytest.raises(ValueError, match="--initial-only was specified"):
        create_librarian_account(
            email="second_safeguard@library.org",
            full_name="Second Safeguard",
            password="SecurePassword456!",
            initial_only=True,
            confirm_additional=True,
            db_session=db,
        )


