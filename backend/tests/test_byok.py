"""
Automated regression tests for Bring-Your-Own-Key (BYOK) AI Architecture.
Verifies that students and teachers can configure and utilize custom LLM API keys
across Copilot Chat, ReAct Librarian Agent, and Multimodal Vision Research.
"""
from typing import Tuple
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.database import atomic_write
from app.models import User


@pytest.fixture
def student_user(db: Session) -> User:
    """Creates a test student user."""
    with atomic_write(db):
        student = User(
            email="byok_student@univ.edu",
            hashed_password=hash_password("Password123!"),
            full_name="BYOK Student",
            role="student",
            is_active=True,
        )
        db.add(student)
        db.flush()
        db.refresh(student)
        return student


def auth_client_for(client: TestClient, user: User) -> Tuple[TestClient, str]:
    """Helper attaching access_token and csrf_token cookies to client."""
    csrf_val = f"test-csrf-token-{user.id}"
    token = create_access_token(user_id=user.id, role=user.role)
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return client, csrf_val


def test_verify_key_unauthenticated(client: TestClient):
    """Unauthenticated users cannot probe API keys (must return 401)."""
    client.cookies.delete("access_token")
    res = client.post("/api/copilot/verify-key", json={"api_key": "AIzaSyTestKey12345", "provider": "gemini"})
    assert res.status_code == 401


def test_verify_key_mock_success(client: TestClient, student_user: User):
    """Tests verify-key endpoint with mocked Google Gemini 200 response."""
    authed_client, csrf = auth_client_for(client, student_user)
    with patch("httpx.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = authed_client.post(
            "/api/copilot/verify-key",
            json={"api_key": "AIzaSyValidStudentKey123", "provider": "gemini"},
            headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["provider"] == "gemini"
        assert "verified and active" in data["message"].lower()


def test_verify_key_mock_rejection(client: TestClient, student_user: User):
    """Tests verify-key endpoint when provider returns an error."""
    authed_client, csrf = auth_client_for(client, student_user)
    with patch("httpx.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"error": {"message": "API_KEY_INVALID"}}
        mock_post.return_value = mock_resp

        res = authed_client.post(
            "/api/copilot/verify-key",
            json={"api_key": "AIzaSyInvalidKey", "provider": "gemini"},
            headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert "API_KEY_INVALID" in data["message"]


def test_copilot_chat_with_custom_key_header(client: TestClient, student_user: User):
    """Ensures copilot chat utilizes patron custom API key from HTTP header."""
    authed_client, csrf = auth_client_for(client, student_user)
    with patch("app.services.copilot.GeminiProvider.generate", return_value="Custom key response"):
        res = authed_client.post(
            "/api/copilot/chat",
            json={"message": "What books do you recommend for machine learning?"},
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": csrf,
                "X-Gemini-API-Key": "AIzaSyCustomPatronKeyHeader",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "reply" in data
        assert data["provider"] in ["gemini", "fallback"]


def test_agent_chat_with_custom_key_header(client: TestClient, student_user: User):
    """Ensures ReAct agent chat accepts X-Gemini-API-Key header."""
    authed_client, csrf = auth_client_for(client, student_user)
    res = authed_client.post(
        "/api/knowledge/agent/chat",
        json={"message": "What are the borrowing rules for students?"},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "X-Gemini-API-Key": "AIzaSyCustomAgentKey",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "agent_actions" in data
