from __future__ import annotations
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from typing import Generator, List, Optional, Tuple, Union
from sqlalchemy import create_engine, event, make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.pool import NullPool

from app.config import (
    get_settings,
    DEFAULT_SQLITE_PATH,
    ROOT_SQLITE_PATH,
    BACKEND_DIR,
    PROJECT_ROOT,
)

settings = get_settings()


class ProtectedDatabaseMigrationError(RuntimeError):
    """
    Raised when an automatic migration attempt targets a protected canonical database
    (backend/library.db or root library.db) without explicit opt-in authorization.
    """
    pass


def is_protected_migration_allowed() -> bool:
    """
    Checks whether the explicit opt-in override for migrating protected databases is active.
    Defaults to False. Activated only when ALLOW_PROTECTED_DB_MIGRATION is set to 'true'.
    """
    import os
    val = os.environ.get("ALLOW_PROTECTED_DB_MIGRATION", "").strip().lower()
    return val in ("true", "1", "yes")


def is_protected_database(database_url: str) -> tuple[bool, Path | None]:
    """
    Determines whether the given database URL or path resolves to any protected canonical database.

    Protected databases:
    1. backend/library.db (canonical development database, revision 0f610073e5f1)
    2. library.db (root baseline database, revision 0f610073e5f1)

    Accounts for:
    - SQLAlchemy make_url parsing and URL formats (e.g. sqlite:///, sqlite://)
    - In-memory databases (:memory:, "") and non-SQLite URLs (not protected file targets)
    - Relative paths, absolute paths, and path traversal ('..')
    - Windows path semantics (case insensitivity, backslashes vs forward slashes)
    - Symlinks, junctions, and reparse points (resolved via Path.resolve())
    """
    from typing import List
    if not database_url:
        return False, None

    try:
        parsed = make_url(database_url)
    except Exception:
        try:
            db_path = Path(database_url)
        except Exception:
            return False, None
    else:
        if "sqlite" not in parsed.drivername:
            return False, None
        if not parsed.database or parsed.database in (":memory:", ""):
            return False, None
        raw_db = parsed.database
        if "?" in raw_db:
            raw_db = raw_db.split("?", 1)[0]
        db_path = Path(raw_db)

    candidates: List[Path] = []
    try:
        candidates.append(db_path.resolve())
    except Exception:
        pass

    if not db_path.is_absolute():
        for base in [Path.cwd(), BACKEND_DIR, PROJECT_ROOT]:
            try:
                candidates.append((base / db_path).resolve())
            except Exception:
                pass

    protected_targets = [DEFAULT_SQLITE_PATH.resolve(), ROOT_SQLITE_PATH.resolve()]

    for cand in candidates:
        cand_norm = cand.as_posix().lower()
        for prot in protected_targets:
            if cand_norm == prot.as_posix().lower():
                return True, cand

    return False, candidates[0] if candidates else None


# Base for SQLAlchemy Models
class Base(DeclarativeBase):
    pass


# ── SQLite Connection and Transaction Handlers ────────────────────────────────
def configure_sqlite_connection(dbapi_conn, _):
    """
    Applied to new DBAPI connections for SQLite:
    - Sets isolation_level = None so SQLAlchemy manages transactions explicitly.
    - Sets foreign_keys = ON to ensure referential integrity.
    - Sets busy_timeout = 5000ms so SQLite handles concurrent lock contention cleanly.
    """
    if isinstance(dbapi_conn, sqlite3.Connection):
        dbapi_conn.isolation_level = None
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()


def handle_engine_begin(conn):
    """
    SQLAlchemy 2.x engine begin handler for SQLite:
    - Does NOT force read-only transactions to acquire a SQLite BEGIN IMMEDIATE write lock.
    - If execution option 'sqlite_immediate' is True, issues BEGIN IMMEDIATE to acquire SQLite's
      reserved lock upfront for write operations (e.g. issuing and returning copies), eliminating
      TOCTOU races.
    - Otherwise, issues a standard deferred BEGIN, allowing concurrent reads to proceed freely
      under WAL mode without acquiring unnecessary write locks.
    """
    if "sqlite" in str(conn.engine.url):
        if conn.get_execution_options().get("sqlite_immediate", False):
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            conn.exec_driver_sql("BEGIN")


def setup_engine_events(target_engine):
    """Attaches connection and transaction begin event listeners to the given engine."""
    event.listen(target_engine, "connect", configure_sqlite_connection)
    event.listen(target_engine, "begin", handle_engine_begin)


# ── Main Application Engine ──────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
setup_engine_events(engine)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a transactional DB session for standard / read operations.
    Uses deferred transactions in SQLite, allowing concurrent reads in WAL mode without
    acquiring write locks.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_write_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a transactional DB session configured specifically
    for write operations (such as book issuing and returning).
    Acquires SQLite's BEGIN IMMEDIATE lock upfront when using SQLite.
    Guarantees session rollback and cleanup if transaction startup or execution fails.
    """
    db = SessionLocal()
    try:
        bind = db.get_bind()
        is_sqlite = bind.dialect.name == "sqlite" if bind else ("sqlite" in settings.DATABASE_URL)
        if is_sqlite:
            db.connection(execution_options={"sqlite_immediate": True})
        db.info["_in_atomic_write"] = True
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.info.pop("_in_atomic_write", None)
        db.close()


@contextmanager
def atomic_write(session: Session) -> Generator[Session, None, None]:
    """
    SQLAlchemy 2.x context manager providing atomic write transactions with SQLite BEGIN IMMEDIATE.

    Transaction ownership rules:
    - The protected read-check-write sequence must execute within one appropriate transaction,
      with BEGIN IMMEDIATE acquired before the relevant reads to prevent TOCTOU races.
    - Does NOT silently commit an existing transaction. If the session already has an active
      non-atomic transaction, raises RuntimeError.
    - If nested within an active atomic_write block, creates a savepoint (begin_nested) to avoid
      accidental nested commits while preserving correct exception propagation.
    - Ensures failed transaction startup triggers rollback and cleanup.
    - Commits the transaction on successful block exit, or rolls back on exception.
    """
    if session.in_transaction():
        if session.info.get("_in_atomic_write", False):
            # Nested atomic_write: use a savepoint to prevent premature root commit
            with session.begin_nested():
                yield session
            return
        else:
            raise RuntimeError(
                "Cannot start atomic_write: session already has an active transaction. "
                "The protected read-check-write sequence must execute within one transaction, "
                "initiated with BEGIN IMMEDIATE before reads."
            )

    session.info["_in_atomic_write"] = True
    bind = session.get_bind()
    is_sqlite = bind.dialect.name == "sqlite" if bind else ("sqlite" in settings.DATABASE_URL)

    try:
        if is_sqlite:
            session.connection(execution_options={"sqlite_immediate": True})
    except Exception:
        session.info.pop("_in_atomic_write", None)
        session.rollback()
        raise

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.info.pop("_in_atomic_write", None)


# Alias for intuitive readability
write_transaction = atomic_write


# ── Alembic Migrations & WAL Initialization Strategy ──────────────────────────
def run_migrations(
    database_url: Optional[str] = None,
    connection=None,
    allow_protected_migration: bool = False,
) -> None:
    """
    Applies all Alembic migrations up to 'head' targeting the specified database,
    making Alembic the consistent schema-management source of truth.

    Safety:
    - Refuses to migrate protected canonical databases (backend/library.db or root library.db)
      unless explicitly authorized via allow_protected_migration=True or ALLOW_PROTECTED_DB_MIGRATION=true.
    """
    if database_url is None:
        database_url = get_settings().DATABASE_URL
    is_protected, target_path = is_protected_database(database_url)
    if is_protected and not allow_protected_migration and not is_protected_migration_allowed():
        raise ProtectedDatabaseMigrationError(
            f"Automatic migration of protected database '{target_path}' is strictly prohibited. "
            f"Attempted schema upgrade targeting protected baseline was blocked. "
            f"To explicitly permit migrating a protected database, pass allow_protected_migration=True "
            f"or set environment variable ALLOW_PROTECTED_DB_MIGRATION=true."
        )

    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    if not ini_path.is_file():
        raise FileNotFoundError(f"Alembic config not found at {ini_path}")

    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    if connection is not None:
        alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")


def init_db(
    database_url: Optional[str] = None,
    connection=None,
    allow_protected_migration: bool = False,
) -> None:
    """
    Idempotent database initialization:
    1. Ensures all ORM models are imported so Base.metadata is registered.
    2. Guardrail: Refuses unsafe automatic migration targeting protected databases
       (backend/library.db or root library.db) unless explicitly authorized.
    3. For file-backed SQLite: Enables WAL mode outside of any active transaction
       using a dedicated NullPool engine that has NO 'begin' event attached.
    4. Verifies that SQLite returns 'wal'.
    5. Handles in-memory SQLite (skips WAL silently).
    6. Applies all Alembic migrations up to 'head' targeting the configured database,
       making Alembic the single consistent schema-management source of truth.
       Safe for repeated startup against fresh or already-migrated databases.
    """
    if database_url is None:
        database_url = get_settings().DATABASE_URL
    is_protected, target_path = is_protected_database(database_url)
    if is_protected and not allow_protected_migration and not is_protected_migration_allowed():
        raise ProtectedDatabaseMigrationError(
            f"Automatic migration of protected database '{target_path}' is strictly prohibited. "
            f"Attempted schema upgrade targeting protected baseline was blocked. "
            f"To explicitly permit migrating a protected database, pass allow_protected_migration=True "
            f"or set environment variable ALLOW_PROTECTED_DB_MIGRATION=true."
        )

    import app.models  # noqa: F401 - ensure models are registered on Base.metadata

    parsed = make_url(database_url)
    is_sqlite = "sqlite" in parsed.drivername
    is_memory = is_sqlite and parsed.database in (":memory:", "", None)

    if is_sqlite and not is_memory:
        # Dedicated initialization engine without the 'begin' listener
        _init_engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

        @event.listens_for(_init_engine, "connect")
        def _configure_init_conn(dbapi_conn, _):
            if isinstance(dbapi_conn, sqlite3.Connection):
                dbapi_conn.isolation_level = None
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON;")
                cursor.execute("PRAGMA busy_timeout = 5000;")
                cursor.close()

        # Check out raw DBAPI connection.
        # Direct execution on pysqlite cursor guarantees zero SQLAlchemy autobegin.
        raw_conn = _init_engine.raw_connection()
        try:
            dbapi_conn: sqlite3.Connection = raw_conn.connection
            cursor = dbapi_conn.cursor()
            result = cursor.execute("PRAGMA journal_mode = WAL;").fetchone()
            cursor.close()

            if not result or result[0].lower() != "wal":
                mode = result[0] if result else "unknown"
                raise RuntimeError(
                    f"PRAGMA journal_mode = WAL was not accepted. SQLite returned '{mode}'. "
                    "Verify that the database file is writable and not locked."
                )
        finally:
            raw_conn.close()
            _init_engine.dispose()

    # Apply Alembic migrations to target database as the schema source of truth
    if is_memory and connection is None:
        target_engine = engine if database_url == settings.DATABASE_URL else create_engine(
            database_url,
            connect_args={"check_same_thread": False} if is_sqlite else {},
        )
        if target_engine is not engine:
            setup_engine_events(target_engine)
        try:
            Base.metadata.create_all(bind=target_engine)
        finally:
            if target_engine is not engine:
                target_engine.dispose()
    else:
        run_migrations(database_url=database_url, connection=connection, allow_protected_migration=allow_protected_migration)


def validate_demo_database(database_url: str = settings.DATABASE_URL) -> None:
    """
    Validates the published demo database for demo mode:
    1. Verifies the database file exists at the canonical demo path.
    2. Opens a read-only SQLite connection to verify structure.
    3. Runs PRAGMA quick_check to verify database integrity.
    4. Runs PRAGMA foreign_key_check to verify foreign key integrity.
    5. Verifies Alembic schema revision matches head ('c3d4e5f6a7b8').

    Invariants:
    - Does NOT automatically create an empty demo database if missing.
    - Does NOT automatically run Alembic migrations during demo startup.
    - Does NOT modify database contents.
    """
    from pathlib import Path
    parsed = make_url(database_url)
    is_sqlite = "sqlite" in parsed.drivername
    if not is_sqlite or not parsed.database or parsed.database in (":memory:", ""):
        raise RuntimeError(
            f"Demo mode requires a file-backed SQLite database. Configured URL: '{database_url}'."
        )

    db_path = Path(parsed.database).resolve()
    if not db_path.is_file():
        raise RuntimeError(
            f"Demo mode startup failed: published demo database not found at '{db_path}'. "
            "Automatic creation of an unpopulated demo database is strictly prohibited."
        )

    # Read-only verification
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        quick_check = cur.execute("PRAGMA quick_check;").fetchall()
        if quick_check != [("ok",)]:
            raise RuntimeError(f"Demo database quick_check failed: {quick_check}")

        fk_check = cur.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_check:
            raise RuntimeError(f"Demo database foreign_key_check reported {len(fk_check)} violations.")

        try:
            rev_row = cur.execute("SELECT version_num FROM alembic_version;").fetchone()
        except sqlite3.OperationalError:
            rev_row = None
        if not rev_row or rev_row[0] != "c3d4e5f6a7b8":
            curr_rev = rev_row[0] if rev_row else "none"
            raise RuntimeError(
                f"Demo database has invalid schema revision '{curr_rev}' (expected 'c3d4e5f6a7b8'). "
                "Automatic migration execution in demo mode is strictly prohibited."
            )
        cur.close()
    finally:
        conn.close()
