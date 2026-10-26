import os
from pathlib import Path
from app.config import find_env_files, Settings


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
