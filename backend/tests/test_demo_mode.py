"""Tests for Stage 6 isolated demo mode configuration and validation."""
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.config import (
    BACKEND_DIR,
    DEFAULT_DATABASE_URL,
    DEMO_DATABASE_URL,
    DEMO_SQLITE_PATH,
    Settings,
)
from app.database import validate_demo_database
from app.main import app


def test_demo_mode_disabled_by_default(monkeypatch):
    """Verifies that demo mode is False by default and targets standard development database."""
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "")
    settings = Settings()
    assert settings.DEMO_MODE is False
    assert settings.DATABASE_URL == DEFAULT_DATABASE_URL


def test_demo_mode_enabled_selects_library_demo_db(monkeypatch):
    """Verifies that setting DEMO_MODE=True automatically targets backend/library_demo.db."""
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "")
    settings = Settings()
    assert settings.DEMO_MODE is True
    assert settings.DATABASE_URL == DEMO_DATABASE_URL
    assert Path(DEMO_SQLITE_PATH).is_file()


def test_demo_mode_rejects_conflicting_database_url(monkeypatch):
    """Verifies that demo mode does NOT silently fall back or accept an unrelated database URL."""
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unrelated_production.db")
    with pytest.raises(ValueError, match="Demo mode conflict"):
        Settings()


def test_validate_demo_database_passes_on_published_db():
    """Verifies that the published library_demo.db satisfies all demo-mode startup checks."""
    assert DEMO_SQLITE_PATH.is_file()
    # Must succeed without exception
    validate_demo_database(DEMO_DATABASE_URL)


def test_validate_demo_database_fails_when_file_missing(tmp_path):
    """Verifies that demo mode startup refuses to create a fresh empty database if missing."""
    missing_file = tmp_path / "missing_demo.db"
    missing_url = f"sqlite:///{missing_file.as_posix()}"
    with pytest.raises(RuntimeError, match="published demo database not found.*Automatic creation.*strictly prohibited"):
        validate_demo_database(missing_url)
    assert not missing_file.exists(), "Missing database was erroneously created!"


def test_validate_demo_database_fails_when_schema_unmigrated(tmp_path):
    """Verifies that demo mode startup refuses to run migrations and rejects unmigrated databases."""
    unmigrated_file = tmp_path / "unmigrated_demo.db"
    conn = sqlite3.connect(str(unmigrated_file))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
    conn.commit()
    conn.close()

    unmigrated_url = f"sqlite:///{unmigrated_file.as_posix()}"
    with pytest.raises(RuntimeError, match="invalid schema revision.*Automatic migration execution.*strictly prohibited"):
        validate_demo_database(unmigrated_url)


def test_demo_mode_health_endpoint(monkeypatch):
    """Verifies that the health check endpoint accurately distinguishes demo mode."""
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "")
    from app.config import get_settings
    get_settings.cache_clear()

    try:
        with TestClient(app) as client:
            resp = client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["environment"] == "demo"
            assert data["demo_mode"] is True
    finally:
        get_settings.cache_clear()
