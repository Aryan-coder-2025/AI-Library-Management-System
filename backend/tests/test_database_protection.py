"""
Unit and regression test suite for protected database guardrails and startup safety.

Verifies:
1. Default startup cannot migrate the protected development DB.
2. Explicitly configured disposable test DBs can still initialize and migrate.
3. Demo startup remains read-only.
4. Conflicting demo database URLs are rejected.
5. Relative and absolute paths resolving to the protected DB are blocked.
6. Symlink aliases resolving to the protected DB are blocked where supported.
7. A missing demo database is rejected rather than silently created.
8. The safety mechanism does not interfere with ordinary test isolation.
"""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.config import (
    DEFAULT_SQLITE_PATH,
    ROOT_SQLITE_PATH,
    DEMO_SQLITE_PATH,
    DEMO_DATABASE_URL,
    DEFAULT_DATABASE_URL,
    Settings,
    get_settings,
)
from app.database import (
    init_db,
    run_migrations,
    validate_demo_database,
    is_protected_database,
    ProtectedDatabaseMigrationError,
)


def sha256_of_file(path: Path) -> str:
    """Calculates SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_default_startup_cannot_migrate_protected_dev_db(monkeypatch):
    """
    1. Default startup cannot migrate the protected development DB.
    Calling init_db() with default arguments (without ALLOW_PROTECTED_DB_MIGRATION)
    must raise ProtectedDatabaseMigrationError.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(ProtectedDatabaseMigrationError) as exc_info:
            init_db()

        msg = str(exc_info.value)
        assert "strictly prohibited" in msg
        assert "ALLOW_PROTECTED_DB_MIGRATION" in msg
    finally:
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        get_settings.cache_clear()


def test_explicit_disposable_test_db_can_initialize_and_migrate(tmp_path: Path):
    """
    2. Explicitly configured disposable test DBs can still initialize and migrate.
    """
    test_db = tmp_path / "disposable_migration_test.db"
    db_url = f"sqlite:///{test_db.as_posix()}"

    # init_db must succeed on disposable test DB
    init_db(database_url=db_url)

    # Verify directly via SQLite
    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    journal_mode = cur.execute("PRAGMA journal_mode;").fetchone()[0]
    rev = cur.execute("SELECT version_num FROM alembic_version;").fetchone()[0]
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    conn.close()

    assert journal_mode.lower() == "wal"
    assert rev == "a1b2c3d4e5f6"
    assert "users" in tables
    assert "books" in tables
    assert "reservations" in tables


def test_demo_startup_remains_read_only(tmp_path: Path):
    """
    3. Demo startup remains read-only.
    Validating the demo database does not alter file content or hash.
    """
    # Test against disposable copy of published demo DB
    test_demo = tmp_path / "disposable_demo.db"
    shutil.copy2(DEMO_SQLITE_PATH, test_demo)

    pre_hash = sha256_of_file(test_demo)
    validate_demo_database(database_url=f"sqlite:///{test_demo.as_posix()}")
    post_hash = sha256_of_file(test_demo)

    assert pre_hash == post_hash, "validate_demo_database altered the database file!"


def test_conflicting_demo_database_urls_rejected(tmp_path: Path):
    """
    4. Conflicting demo database URLs are rejected.
    """
    conflict_db = tmp_path / "conflicting_demo.db"
    with pytest.raises(ValueError) as exc_info:
        Settings(
            DEMO_MODE=True,
            DATABASE_URL=f"sqlite:///{conflict_db.as_posix()}",
            JWT_SECRET_KEY="test-secret-key-32-chars-long-for-testing",
        )
    assert "Demo mode conflict" in str(exc_info.value)


@pytest.mark.parametrize(
    "url_variant",
    [
        f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}",
        f"sqlite:///{ROOT_SQLITE_PATH.as_posix()}",
        "sqlite:///backend/library.db",
        "sqlite:///library.db",
        "sqlite:///./backend/library.db",
        "sqlite:///./library.db",
    ],
)
def test_relative_and_absolute_paths_to_protected_db_blocked(url_variant: str):
    """
    5. Relative and absolute paths resolving to the protected DB are blocked.
    """
    with pytest.raises(ProtectedDatabaseMigrationError):
        init_db(database_url=url_variant)

    with pytest.raises(ProtectedDatabaseMigrationError):
        run_migrations(database_url=url_variant)


def test_symlink_aliases_to_protected_db_blocked(tmp_path: Path):
    """
    6. Symlink aliases resolving to the protected DB are blocked where supported.
    """
    symlink_file = tmp_path / "symlink_to_protected.db"
    try:
        symlink_file.symlink_to(DEFAULT_SQLITE_PATH)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported in current environment/permissions.")

    assert symlink_file.is_symlink()
    symlink_url = f"sqlite:///{symlink_file.as_posix()}"

    with pytest.raises(ProtectedDatabaseMigrationError):
        init_db(database_url=symlink_url)

    with pytest.raises(ProtectedDatabaseMigrationError):
        run_migrations(database_url=symlink_url)


def test_missing_demo_database_rejected_rather_than_created(tmp_path: Path):
    """
    7. A missing demo database is rejected rather than silently created.
    """
    missing_demo = tmp_path / "missing_demo.db"
    assert not missing_demo.exists()

    with pytest.raises(RuntimeError) as exc_info:
        validate_demo_database(database_url=f"sqlite:///{missing_demo.as_posix()}")

    assert "published demo database not found" in str(exc_info.value)
    assert not missing_demo.exists(), "validate_demo_database silently created an empty database file!"


def test_safety_mechanism_does_not_interfere_with_test_isolation():
    """
    8. The safety mechanism does not interfere with ordinary test isolation.
    In-memory databases can be initialized without being blocked.
    """
    is_prot, _ = is_protected_database("sqlite:///:memory:")
    assert is_prot is False

    is_prot_empty, _ = is_protected_database("sqlite://")
    assert is_prot_empty is False

    # Calling init_db on in-memory database must succeed
    init_db(database_url="sqlite:///:memory:")


def test_explicit_opt_in_allows_migration_override(tmp_path: Path, monkeypatch):
    """
    Proves that the separate explicit opt-in mechanism works when authorized,
    tested against a temporary sandbox database.
    """
    disposable_dev = tmp_path / "simulated_dev.db"
    disposable_url = f"sqlite:///{disposable_dev.as_posix()}"

    # Simulate disposable_dev as a protected path
    monkeypatch.setattr(
        "app.database.DEFAULT_SQLITE_PATH",
        disposable_dev.resolve(),
    )

    # Without override -> blocked
    with pytest.raises(ProtectedDatabaseMigrationError):
        init_db(database_url=disposable_url)

    # With parameter override -> allowed
    init_db(database_url=disposable_url, allow_protected_migration=True)
    assert disposable_dev.is_file()

    # With environment variable override -> allowed
    disposable_env = tmp_path / "simulated_env.db"
    disposable_env_url = f"sqlite:///{disposable_env.as_posix()}"
    monkeypatch.setattr("app.database.DEFAULT_SQLITE_PATH", disposable_env.resolve())
    monkeypatch.setenv("ALLOW_PROTECTED_DB_MIGRATION", "true")

    init_db(database_url=disposable_env_url)
    assert disposable_env.is_file()
