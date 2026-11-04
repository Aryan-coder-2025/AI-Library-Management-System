import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_SQLITE_PATH = (BACKEND_DIR / "library.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
ROOT_SQLITE_PATH = (PROJECT_ROOT / "library.db").resolve()
DEMO_SQLITE_PATH = (BACKEND_DIR / "library_demo.db").resolve()
DEMO_DATABASE_URL = f"sqlite:///{DEMO_SQLITE_PATH.as_posix()}"


def get_default_database_url() -> str:
    """
    Returns the deterministic, absolute file-backed SQLite database URL
    anchored to the backend directory (backend/library.db).
    """
    return DEFAULT_DATABASE_URL


def get_demo_database_url() -> str:
    """
    Returns the deterministic, absolute file-backed SQLite database URL
    anchored to the published demo database (backend/library_demo.db).
    """
    return DEMO_DATABASE_URL


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
    DEMO_MODE: bool = False

    # Database (anchored to backend/library.db by default)
    DATABASE_URL: str = DEFAULT_DATABASE_URL

    # Security
    JWT_SECRET_KEY: str = Field(..., description="JWT signing secret key must be set")
    SPACES_QR_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Dedicated signing secret key for study space QR passes. Must be distinct from JWT_SECRET_KEY.",
    )
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

    # AI Copilot & LLM Configuration
    LLM_PROVIDER: str = "auto"  # 'auto', 'gemini', 'openai_compatible', 'fallback'
    LLM_API_KEY: Optional[str] = None
    LLM_API_URL: Optional[str] = None
    LLM_MODEL_NAME: str = "gemini-1.5-flash"
    COPILOT_MAX_QUERY_LENGTH: int = 500
    COPILOT_TIMEOUT_SECONDS: float = 12.0

    # Study Space & Reservation Configuration
    LIBRARY_TIMEZONE: str = "Asia/Kolkata"
    LIBRARY_OPEN_TIME: str = "08:00"
    LIBRARY_CLOSE_TIME: str = "22:00"
    MIN_RESERVATION_DURATION_MINUTES: int = 30
    MAX_SEAT_RESERVATION_HOURS: int = 4
    MAX_ROOM_RESERVATION_HOURS: int = 3
    STUDENT_MAX_ACTIVE_RESERVATIONS: int = 1
    TEACHER_MAX_ACTIVE_RESERVATIONS: int = 2
    STUDENT_ADVANCE_BOOKING_DAYS: int = 7
    TEACHER_ADVANCE_BOOKING_DAYS: int = 14
    LIBRARIAN_ADVANCE_BOOKING_DAYS: int = 30
    CHECKIN_WINDOW_BEFORE_MINUTES: int = 15
    CHECKIN_GRACE_PERIOD_MINUTES: int = 15
    NO_SHOW_GRACE_PERIOD_MINUTES: int = 15

    @model_validator(mode="after")
    def resolve_mode_and_database(self) -> "Settings":
        if self.SPACES_QR_SECRET_KEY and self.JWT_SECRET_KEY:
            if self.SPACES_QR_SECRET_KEY.strip() == self.JWT_SECRET_KEY.strip():
                raise ValueError("SPACES_QR_SECRET_KEY must be distinct from JWT_SECRET_KEY.")

        if self.DEMO_MODE:
            # If DATABASE_URL was left default, switch to canonical published demo database
            if self.DATABASE_URL == DEFAULT_DATABASE_URL:
                self.DATABASE_URL = DEMO_DATABASE_URL
            else:
                # If explicitly set in demo mode, ensure it targets the published demo database
                try:
                    from sqlalchemy import make_url
                    parsed = make_url(self.DATABASE_URL)
                    if not (parsed.database and Path(parsed.database).resolve() == DEMO_SQLITE_PATH):
                        raise ValueError(
                            f"Demo mode conflict: DEMO_MODE is True, but DATABASE_URL '{self.DATABASE_URL}' "
                            f"does not resolve to canonical demo database '{DEMO_SQLITE_PATH}'."
                        )
                except Exception as exc:
                    if isinstance(exc, ValueError) and "Demo mode conflict" in str(exc):
                        raise
                    raise ValueError(f"Invalid DATABASE_URL in demo mode: {exc}") from exc
        return self

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: Optional[str]) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return DEFAULT_DATABASE_URL
        return v

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
