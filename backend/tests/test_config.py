import os
from pathlib import Path
from sqlalchemy import make_url

from app.config import (
    BACKEND_DIR,
    PROJECT_ROOT,
    DEFAULT_SQLITE_PATH,
    DEFAULT_DATABASE_URL,
    get_default_database_url,
    find_env_files,
    Settings,
)


def test_find_env_files_locates_root_env():
    """
    Verifies that find_env_files discovers the project root .env file.
    """
    files = find_env_files()
    assert len(files) >= 1
    assert any(p.name == ".env" for p in files)


def test_settings_loads_jwt_secret_regardless_of_cwd(monkeypatch, tmp_path):
    """
    Verifies that Settings can be instantiated when working directory is changed
    to an arbitrary directory without losing access to .env.
    """
    # Change working directory to an isolated temp folder
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.JWT_SECRET_KEY is not None
    assert len(settings.JWT_SECRET_KEY) > 0


def test_default_database_resolution_independent_of_cwd(monkeypatch, tmp_path):
    """
    Verifies that default database resolution produces the exact same absolute URL
    anchored to backend/library.db regardless of whether the process runs from
    the repository root, backend directory, or an arbitrary temporary directory.
    """
    # Set DATABASE_URL to empty string so environment overrides any local .env file
    # and invokes assemble_database_url's default resolution.
    monkeypatch.setenv("DATABASE_URL", "")

    # 1. From an isolated temporary directory
    monkeypatch.chdir(tmp_path)
    settings_temp = Settings()
    parsed_temp = make_url(settings_temp.DATABASE_URL)
    assert Path(parsed_temp.database).resolve() == (BACKEND_DIR / "library.db").resolve()

    # 2. From the repository root
    monkeypatch.chdir(PROJECT_ROOT)
    settings_root = Settings()
    parsed_root = make_url(settings_root.DATABASE_URL)
    assert Path(parsed_root.database).resolve() == (BACKEND_DIR / "library.db").resolve()

    # 3. From the backend directory
    monkeypatch.chdir(BACKEND_DIR)
    settings_backend = Settings()
    parsed_backend = make_url(settings_backend.DATABASE_URL)
    assert Path(parsed_backend.database).resolve() == (BACKEND_DIR / "library.db").resolve()

    # All three resolve to the exact same URL
    assert settings_temp.DATABASE_URL == settings_root.DATABASE_URL == settings_backend.DATABASE_URL
    assert settings_root.DATABASE_URL == DEFAULT_DATABASE_URL


def test_explicit_configured_database_url_overrides_default(monkeypatch):
    """
    Verifies that an explicitly configured DATABASE_URL (via environment or kwargs)
    takes precedence over the anchored default.
    """
    custom_url = "sqlite:///custom_override.db"
    monkeypatch.setenv("DATABASE_URL", custom_url)
    settings_env = Settings()
    assert settings_env.DATABASE_URL == custom_url

    # Constructor override
    explicit_arg_url = "sqlite:///arg_override.db"
    settings_arg = Settings(DATABASE_URL=explicit_arg_url)
    assert settings_arg.DATABASE_URL == explicit_arg_url


def test_temporary_test_database_configuration_supported(monkeypatch, tmp_path):
    """
    Verifies that test configurations using in-memory or temporary file-backed SQLite
    continue to be supported without interference.
    """
    # 1. In-memory database
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    settings_mem = Settings()
    assert settings_mem.DATABASE_URL == "sqlite:///:memory:"

    # 2. Temporary file database
    temp_file = tmp_path / "isolated_test.db"
    temp_url = f"sqlite:///{temp_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", temp_url)
    settings_file = Settings()
    assert settings_file.DATABASE_URL == temp_url
    assert Path(make_url(settings_file.DATABASE_URL).database).resolve() == temp_file.resolve()


def test_resolved_default_path_points_to_backend_library_db_not_root(monkeypatch):
    """
    Verifies that the resolved default database file specifically targets backend/library.db
    and does NOT resolve to root/library.db.
    """
    # Set DATABASE_URL to empty string so environment overrides any local .env file
    # and invokes assemble_database_url's default resolution.
    monkeypatch.setenv("DATABASE_URL", "")
    settings = Settings()
    resolved_db_path = Path(make_url(settings.DATABASE_URL).database).resolve()

    backend_expected = (BACKEND_DIR / "library.db").resolve()
    root_avoided = (PROJECT_ROOT / "library.db").resolve()

    assert resolved_db_path == backend_expected
    assert resolved_db_path != root_avoided
    assert resolved_db_path.name == "library.db"
    assert resolved_db_path.parent == BACKEND_DIR

