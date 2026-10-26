import os
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


def find_env_files() -> Tuple[Path, ...]:
    """
    Discovers candidate .env files regardless of the process working directory:
    1. Project root directory (.env at repo root)
    2. Backend directory (.env in backend/)
    3. Current working directory (.env in cwd)
    4. Custom path via ENV_FILE environment variable (if specified)

    Preserves precedence: later files in the sequence override earlier ones.
    """
    candidates: List[Path] = []

    # 1. Project root .env (base configuration)
    root_env = (PROJECT_ROOT / ".env").resolve()
    if root_env.is_file():
        candidates.append(root_env)

    # 2. Backend directory .env (backend-specific overrides)
    backend_env = (BACKEND_DIR / ".env").resolve()
    if backend_env.is_file() and backend_env not in candidates:
        candidates.append(backend_env)

    # 3. Current working directory .env (working directory overrides)
    cwd_env = (Path.cwd() / ".env").resolve()
    if cwd_env.is_file() and cwd_env not in candidates:
        candidates.append(cwd_env)

    # 4. Custom ENV_FILE override
    if "ENV_FILE" in os.environ:
        custom_env = Path(os.environ["ENV_FILE"]).resolve()
        if custom_env.is_file() and custom_env not in candidates:
            candidates.append(custom_env)

    # Fallback to standard relative paths if no candidate file exists yet
    if not candidates:
        return (root_env, backend_env, Path(".env"))

    return tuple(candidates)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and discovered .env files.

    Expected startup commands:
      - From project root:
          uvicorn backend.app.main:app --reload
      - From backend directory:
          uvicorn app.main:app --reload
    """
    model_config = SettingsConfigDict(
        env_file=find_env_files(),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "AI Library Management System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./library.db"

    # Security
    JWT_SECRET_KEY: str = Field(..., description="JWT signing secret key must be set")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # CORS & CSRF Whitelist
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Cookie settings
    COOKIE_DOMAIN: str = ""
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
