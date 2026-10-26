import sqlite3
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event, make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()


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
def run_migrations(database_url: str = settings.DATABASE_URL, connection=None) -> None:
    """
    Applies all Alembic migrations up to 'head' targeting the specified database,
    making Alembic the consistent schema-management source of truth.
    """
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


def init_db(database_url: str = settings.DATABASE_URL, connection=None) -> None:
    """
    Idempotent database initialization:
    1. Ensures all ORM models are imported so Base.metadata is registered.
    2. For file-backed SQLite: Enables WAL mode outside of any active transaction
       using a dedicated NullPool engine that has NO 'begin' event attached.
    3. Verifies that SQLite returns 'wal'.
    4. Handles in-memory SQLite (skips WAL silently).
    5. Applies all Alembic migrations up to 'head' targeting the configured database,
       making Alembic the single consistent schema-management source of truth.
       Safe for repeated startup against fresh or already-migrated databases.
    """
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
        run_migrations(database_url=database_url, connection=connection)
