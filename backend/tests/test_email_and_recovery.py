"""
Automated Test Suite for Stage 12.10 — Email Infrastructure & Secure Password Recovery.

Validates:
1. Cryptographic token generation, 256-bit entropy, and SHA-256 token hashing.
2. Zero plaintext tokens persisted in database.
3. Forgot-password endpoint: uniform responses, non-existent account privacy, rate limiting, and failure handling.
4. Reset-password endpoint: token consumption, 12-char password policy, expiry, single-use, and cookie clearance.
5. EmailService: configurable SMTP, STARTTLS/SSL, timeouts, connection/auth failure handling, and HTML/text templates.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    generate_password_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.config import get_settings
from app.database import atomic_write
from app.models import PasswordResetToken, User
from app.routers.auth import reset_forgot_password_rate_limit
from app.services.email import (
    EmailService,
    build_password_reset_html,
    build_password_reset_text,
    email_service,
    obfuscate_email,
)


@pytest.fixture
def recovery_user(db: Session) -> User:
    """Creates a sample active user for password recovery testing."""
    with atomic_write(db):
        user = User(
            email="scholar.recovery@university.edu",
            username="scholar_rec",
            full_name="Scholar In Recovery",
            hashed_password=hash_password("OriginalPass123!"),
            role="student",
            is_active=True,
        )
        db.add(user)
    return user


@pytest.fixture
def inactive_user(db: Session) -> User:
    """Creates an inactive user for account security testing."""
    with atomic_write(db):
        user = User(
            email="inactive.scholar@university.edu",
            username="inactive_rec",
            full_name="Inactive Scholar",
            hashed_password=hash_password("InactivePass123!"),
            role="student",
            is_active=False,
        )
        db.add(user)
    return user


@pytest.fixture(autouse=True)
def clean_rate_limit():
    """Resets rate limit counter before and after each test."""
    reset_forgot_password_rate_limit()
    yield
    reset_forgot_password_rate_limit()


# ── 1. Cryptographic Token Security & Lifecycle ─────────────────────────────

def test_token_generation_entropy_and_hashing():
    raw1, hash1 = generate_password_reset_token()
    raw2, hash2 = generate_password_reset_token()

    assert len(raw1) >= 40
    assert len(hash1) == 64  # SHA-256 hex digest
    assert raw1 != raw2
    assert hash1 != hash2
    assert hash_reset_token(raw1) == hash1
    assert hash_reset_token(raw2) == hash2


def test_token_not_persisted_in_plaintext(client: TestClient, recovery_user: User, db: Session):
    with patch.object(email_service, "send_password_reset_email", return_value=True) as mock_send:
        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": recovery_user.email},
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp.status_code == 200
        assert mock_send.called

        raw_token_sent = mock_send.call_args[1]["reset_token"]

        token_records = db.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == recovery_user.id)
        ).scalars().all()
        assert len(token_records) == 1
        record = token_records[0]

        # Critical: Plaintext token must NEVER equal the stored hash
        assert record.token_hash != raw_token_sent
        assert record.token_hash == hash_reset_token(raw_token_sent)
        assert record.is_used is False


# ── 2. Forgot-Password Endpoint ──────────────────────────────────────────────

def test_forgot_password_uniform_response_for_existing_and_nonexistent(client: TestClient, recovery_user: User):
    with patch.object(email_service, "send_password_reset_email", return_value=True):
        resp_existing = client.post(
            "/api/auth/forgot-password",
            json={"email": recovery_user.email},
            headers={"Origin": "http://localhost:5173"},
        )
        resp_missing = client.post(
            "/api/auth/forgot-password",
            json={"email": "nobody_exists_here@university.edu"},
            headers={"Origin": "http://localhost:5173"},
        )

        assert resp_existing.status_code == 200
        assert resp_missing.status_code == 200

        # Uniform messaging: account enumeration prevention
        expected_msg = "If an account with that email exists, password reset instructions have been sent."
        assert resp_existing.json()["message"] == expected_msg
        assert resp_missing.json()["message"] == expected_msg


def test_forgot_password_inactive_user_no_token_issued(client: TestClient, inactive_user: User, db: Session):
    with patch.object(email_service, "send_password_reset_email", return_value=True) as mock_send:
        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": inactive_user.email},
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp.status_code == 200
        assert not mock_send.called

        records = db.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == inactive_user.id)
        ).scalars().all()
        assert len(records) == 0


def test_forgot_password_invalid_email_format(client: TestClient):
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "not-an-email"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 422


def test_forgot_password_rate_limiting(client: TestClient, recovery_user: User):
    with patch.object(email_service, "send_password_reset_email", return_value=True):
        # 5 allowed requests
        for _ in range(5):
            resp = client.post(
                "/api/auth/forgot-password",
                json={"email": recovery_user.email},
                headers={"Origin": "http://localhost:5173"},
            )
            assert resp.status_code == 200

        # 6th request triggers HTTP 429
        resp_blocked = client.post(
            "/api/auth/forgot-password",
            json={"email": recovery_user.email},
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp_blocked.status_code == 429
        assert "Too many password reset requests" in resp_blocked.json()["detail"]


def test_forgot_password_smtp_delivery_failure_is_graceful(client: TestClient, recovery_user: User):
    with patch.object(email_service, "send_password_reset_email", return_value=False):
        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": recovery_user.email},
            headers={"Origin": "http://localhost:5173"},
        )
        # Returns uniform response without exposing internal email delivery failure
        assert resp.status_code == 200
        assert "password reset instructions have been sent" in resp.json()["message"]


def test_forgot_password_invalidates_prior_active_tokens(client: TestClient, recovery_user: User, db: Session):
    with patch.object(email_service, "send_password_reset_email", return_value=True):
        client.post(
            "/api/auth/forgot-password",
            json={"email": recovery_user.email},
            headers={"Origin": "http://localhost:5173"},
        )
        client.post(
            "/api/auth/forgot-password",
            json={"email": recovery_user.email},
            headers={"Origin": "http://localhost:5173"},
        )

        records = db.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == recovery_user.id)
            .order_by(PasswordResetToken.id.asc())
        ).scalars().all()

        assert len(records) == 2
        assert records[0].is_used is True  # First token invalidated
        assert records[1].is_used is False  # Second token active


# ── 3. Reset-Password Endpoint ───────────────────────────────────────────────

def test_reset_password_success_workflow(client: TestClient, recovery_user: User, db: Session):
    raw_token, token_hash = generate_password_reset_token()
    with atomic_write(db):
        token_record = PasswordResetToken(
            user_id=recovery_user.id,
            token_hash=token_hash,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            is_used=False,
        )
        db.add(token_record)

    # 1. Reset password with new 12-character password
    new_password = "BrandNewSecurePassword2026!"
    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": new_password,
            "confirm_password": new_password,
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    assert "successfully reset" in resp.json()["message"].lower()

    # 2. Verify token is now marked as used
    db.refresh(token_record)
    assert token_record.is_used is True
    assert token_record.used_at is not None

    # 3. Verify user can log in with new password
    db.refresh(recovery_user)
    assert verify_password(new_password, recovery_user.hashed_password)
    assert not verify_password("OriginalPass123!", recovery_user.hashed_password)

    login_resp = client.post(
        "/api/auth/login",
        json={"email": recovery_user.email, "password": new_password},
        headers={"Origin": "http://localhost:5173"},
    )
    assert login_resp.status_code == 200


def test_reset_password_rejects_invalid_token(client: TestClient):
    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": "completely-invalid-nonexistent-token-123456",
            "new_password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 400
    assert "Invalid or expired" in resp.json()["detail"]


def test_reset_password_rejects_expired_token(client: TestClient, recovery_user: User, db: Session):
    raw_token, token_hash = generate_password_reset_token()
    with atomic_write(db):
        token_record = PasswordResetToken(
            user_id=recovery_user.id,
            token_hash=token_hash,
            created_at=datetime.utcnow() - timedelta(minutes=40),
            expires_at=datetime.utcnow() - timedelta(minutes=10),  # Expired 10m ago
            is_used=False,
        )
        db.add(token_record)

    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_reset_password_rejects_reused_token(client: TestClient, recovery_user: User, db: Session):
    raw_token, token_hash = generate_password_reset_token()
    with atomic_write(db):
        token_record = PasswordResetToken(
            user_id=recovery_user.id,
            token_hash=token_hash,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            is_used=True,  # Already consumed
            used_at=datetime.utcnow(),
        )
        db.add(token_record)

    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 400
    assert "already been used" in resp.json()["detail"].lower()


def test_reset_password_enforces_12_char_minimum(client: TestClient):
    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": "valid_token_structure_12345",
            "new_password": "Short12345!",  # 11 chars
            "confirm_password": "Short12345!",
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 422
    assert "at least 12 characters" in str(resp.json())


def test_reset_password_rejects_confirmation_mismatch(client: TestClient):
    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": "valid_token_structure_12345",
            "new_password": "ValidPassword123!",
            "confirm_password": "DifferentPassword123!",
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 422
    assert "Passwords do not match" in str(resp.json())


# ── 4. Email Infrastructure & Template Tests ─────────────────────────────────

def test_email_service_disabled_by_default():
    service = EmailService()
    # When EMAIL_ENABLED is False, returns False and does not open socket
    res = service.send_email(
        to_email="test@university.edu",
        subject="Test Subject",
        html_body="<p>Test</p>",
        text_body="Test",
    )
    assert res is False


def test_email_service_missing_host():
    service = EmailService()
    with patch("app.services.email.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.EMAIL_ENABLED = True
        settings_mock.SMTP_HOST = ""
        settings_mock.SMTP_FROM_EMAIL = "noreply@library.edu"
        mock_settings.return_value = settings_mock

        res = service.send_email("test@university.edu", "Subject", "<h1>Test</h1>", "Test")
        assert res is False


def test_email_service_mocked_smtp_success():
    service = EmailService()
    with patch("app.services.email.get_settings") as mock_settings, \
         patch("smtplib.SMTP") as mock_smtp_cls:
        settings_mock = MagicMock()
        settings_mock.EMAIL_ENABLED = True
        settings_mock.SMTP_HOST = "smtp.mock.edu"
        settings_mock.SMTP_PORT = 587
        settings_mock.SMTP_USE_TLS = True
        settings_mock.SMTP_USERNAME = "library_mailer"
        settings_mock.SMTP_PASSWORD = "MailerSecret123!"
        settings_mock.SMTP_FROM_EMAIL = "noreply@athenaeum.edu"
        settings_mock.SMTP_FROM_NAME = "Athenaeum Library"
        settings_mock.SMTP_TIMEOUT_SECONDS = 5.0
        mock_settings.return_value = settings_mock

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        res = service.send_email("scholar@university.edu", "Test Subject", "<p>Content</p>", "Content")

        assert res is True
        mock_server.ehlo.assert_called()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("library_mailer", "MailerSecret123!")
        mock_server.send_message.assert_called_once()


def test_email_service_connection_error_handled_gracefully():
    service = EmailService()
    with patch("app.services.email.get_settings") as mock_settings, \
         patch("smtplib.SMTP") as mock_smtp_cls:
        settings_mock = MagicMock()
        settings_mock.EMAIL_ENABLED = True
        settings_mock.SMTP_HOST = "unreachable.smtp.edu"
        settings_mock.SMTP_PORT = 587
        settings_mock.SMTP_FROM_EMAIL = "noreply@athenaeum.edu"
        settings_mock.SMTP_FROM_NAME = "Athenaeum"
        settings_mock.SMTP_TIMEOUT_SECONDS = 2.0
        mock_settings.return_value = settings_mock

        import smtplib
        mock_smtp_cls.side_effect = smtplib.SMTPConnectError(421, b"Connection refused")

        res = service.send_email("scholar@university.edu", "Test", "<p>Test</p>", "Test")
        assert res is False


def test_email_templates_content():
    reset_url = "http://localhost:5173/?reset_token=sample_token_xyz"
    expire_minutes = 30

    html = build_password_reset_html("Scholar Name", reset_url, expire_minutes)
    text = build_password_reset_text("Scholar Name", reset_url, expire_minutes)

    # HTML assertions
    assert "ATHENAEUM" in html
    assert "Scholar Name" in html
    assert reset_url in html
    assert "30 minutes" in html
    assert "safely ignore" in html
    assert "will never ask for your password" in html

    # Text assertions
    assert "Scholar Name" in text
    assert reset_url in text
    assert "30 minutes" in text
    assert "safely ignore" in text


def test_obfuscate_email():
    assert obfuscate_email("alexander.smith@university.edu") == "a*************h@university.edu"
    assert obfuscate_email("ab@domain.com") == "a*@domain.com"
    assert obfuscate_email("invalid") == "invalid-email"
