from pathlib import Path
import sqlite3
from alembic.config import Config
from alembic import command
from sqlalchemy import inspect, create_engine, select
from sqlalchemy.orm import Session
from app.database import init_db
from app.models import Base, User


def test_alembic_migration_head(tmp_path: Path):
    """
    Verifies that Alembic can apply all migrations from base to head on a fresh
    database and that all expected tables and indexes are created.
    """
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"

    # Path to alembic.ini
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    assert ini_path.is_file(), f"alembic.ini not found at {ini_path}"

    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head
    command.upgrade(cfg, "head")

    # 2. Inspect created tables
    engine = create_engine(db_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {"users", "books", "book_copies", "loans", "alembic_version"}
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"

    # Verify unique partial index on loans
    loan_indexes = {idx["name"]: idx for idx in inspector.get_indexes("loans")}
    assert "uix_one_active_loan_per_copy" in loan_indexes
    assert bool(loan_indexes["uix_one_active_loan_per_copy"]["unique"]) is True

    engine.dispose()


def test_init_db_runs_migrations_on_fresh_database(tmp_path: Path):
    """
    Verifies that init_db() applies Alembic migrations on a fresh file-backed database,
    ensuring WAL mode is set before migrations and alembic_version + schema tables exist.
    """
    db_file = tmp_path / "fresh_app.db"
    db_url = f"sqlite:///{db_file}"

    # Execute init_db on fresh database
    init_db(database_url=db_url)

    # 1. Verify WAL mode
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
    cursor.close()
    conn.close()

    assert journal_mode.lower() == "wal"
    expected_tables = {"alembic_version", "users", "books", "book_copies", "loans"}
    assert expected_tables.issubset(tables)


def test_init_db_repeated_startup_on_already_migrated_database(tmp_path: Path):
    """
    Verifies that calling init_db() against an already-migrated database is completely safe,
    idempotent, and preserves existing data without errors.
    """
    db_file = tmp_path / "repeated_app.db"
    db_url = f"sqlite:///{db_file}"

    # First initialization
    init_db(database_url=db_url)

    # Insert test data into the migrated database
    engine = create_engine(db_url)
    with Session(engine) as session:
        user = User(
            email="existing_librarian@library.org",
            hashed_password="hashed_pw_test",
            full_name="Existing Librarian",
            role="librarian",
        )
        session.add(user)
        session.commit()
    engine.dispose()

    # Second initialization (simulating server restart)
    init_db(database_url=db_url)

    # Verify existing data is preserved and schema is intact
    engine2 = create_engine(db_url)
    with Session(engine2) as session:
        saved_user = session.execute(
            select(User).where(User.email == "existing_librarian@library.org")
        ).scalar_one_or_none()
        assert saved_user is not None
        assert saved_user.full_name == "Existing Librarian"
    engine2.dispose()
