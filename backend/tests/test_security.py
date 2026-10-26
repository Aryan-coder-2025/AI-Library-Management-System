import secrets
import pytest


def test_safe_methods_bypass_csrf_check(client):
    """
    GET, HEAD, and OPTIONS requests should never be blocked by CSRF middleware.
    """
    response = client.get("/api/health")
    assert response.status_code == 200


def test_disallowed_origin_rejected_on_state_change(client):
    """
    State-changing methods from disallowed origins must be rejected with 403.
    """
    response = client.post(
        "/api/health",
        headers={"Origin": "http://malicious-site.com"},
    )
    assert response.status_code == 403
    assert "not permitted" in response.json()["detail"]


def test_allowed_origin_without_csrf_token_rejected_on_protected_post(client):
    """
    Non-exempt mutation endpoints must reject requests with missing CSRF tokens.
    """
    response = client.post(
        "/api/health",  # /api/health with POST is not exempt from CSRF
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_mismatched_csrf_token_rejected(client):
    """
    Requests with mismatched cookie and X-CSRF-Token header must be rejected.
    """
    client.cookies.set("csrf_token", "correct-token-value")
    response = client.post(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": "different-token-value",
        },
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]
