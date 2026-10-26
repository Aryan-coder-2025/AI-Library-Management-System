import sqlite3
import threading
import time
from datetime import date, timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, select, Engine, event, inspect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.database import (
    init_db,
    atomic_write,
    get_db,
    get_write_db,
    setup_engine_events,
    Base,
)
from app.models import User, Book, BookCopy, Loan


def test_wal_enabled_without_begin_immediate(tmp_path: Path):
    """
    Verifies that WAL mode is enabled outside of any active transaction
    during the actual init_db() execution on a temporary file-backed SQLite database.
    Uses SQLite's native trace callback via SQLAlchemy's Engine connect event to assert
    that no transaction-start statement (BEGIN / BEGIN IMMEDIATE) occurs before or during
    PRAGMA journal_mode = WAL.
    """
    db_file = tmp_path / "test_wal_init.db"
    db_url = f"sqlite:///{db_file}"

    executed_statements: list[str] = []

    def trace_listener(dbapi_conn, _):
        if isinstance(dbapi_conn, sqlite3.Connection):
            dbapi_conn.set_trace_callback(lambda stmt: executed_statements.append(stmt.strip()))

    event.listen(Engine, "connect", trace_listener)
    try:
        init_db(database_url=db_url)
    finally:
        event.remove(Engine, "connect", trace_listener)

    # 1. Normalize recorded statements
    normalized = [stmt.upper() for stmt in executed_statements]

    # 2. Locate PRAGMA journal_mode = WAL
    wal_indices = [
        idx for idx, stmt in enumerate(normalized)
        if "PRAGMA JOURNAL_MODE" in stmt and "WAL" in stmt
    ]
    assert len(wal_indices) >= 1, f"PRAGMA journal_mode = WAL was not executed. Statements: {executed_statements}"
    wal_idx = wal_indices[0]

    # 3. Assert no transaction-start statement occurred before or during WAL pragma
    statements_before_wal = normalized[:wal_idx]
    for stmt in statements_before_wal:
        assert not stmt.startswith("BEGIN"), (
            f"Transaction statement '{stmt}' occurred before PRAGMA journal_mode = WAL."
        )

    # 4. Verify that the actual initialization path succeeded
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    cursor.close()
    conn.close()

    assert journal_mode.lower() == "wal"
    assert {"users", "books", "book_copies", "loans"}.issubset(set(tables))


def test_init_db_file_backed(tmp_path: Path):
    """
    Verifies that init_db(database_url=...) configures WAL mode and creates
    the full set of expected ORM tables in the EXACT specified file-backed database.
    """
    db_file = tmp_path / "app_init.db"
    db_url = f"sqlite:///{db_file}"

    init_db(database_url=db_url)

    # Verify directly on the SQLite file
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
    cursor.close()
    conn.close()

    assert mode.lower() == "wal"
    expected_tables = {"users", "books", "book_copies", "loans"}
    assert expected_tables.issubset(tables), f"Missing tables in {db_file}: {expected_tables - tables}"


def test_read_vs_write_transaction_behavior(tmp_path: Path):
    """
    Verifies that standard read transactions do NOT issue BEGIN IMMEDIATE,
    while atomic_write blocks DO issue BEGIN IMMEDIATE.
    """
    db_file = tmp_path / "test_txn_behavior.db"
    db_url = f"sqlite:///{db_file}"
    init_db(database_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    setup_engine_events(engine)

    # Track DBAPI statements
    read_statements: list[str] = []
    write_statements: list[str] = []

    # 1. Execute read query with standard session
    with engine.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        dbapi.set_trace_callback(lambda stmt: read_statements.append(stmt.strip()))
        with Session(bind=conn) as session:
            session.execute(select(Book)).all()
        dbapi.set_trace_callback(None)

    normalized_read = [s.upper() for s in read_statements]
    assert any("SELECT" in s for s in normalized_read)
    assert not any("BEGIN IMMEDIATE" in s for s in normalized_read), (
        f"Read transaction unexpectedly executed BEGIN IMMEDIATE: {read_statements}"
    )

    # 2. Execute write query with atomic_write
    with engine.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        dbapi.set_trace_callback(lambda stmt: write_statements.append(stmt.strip()))
        with Session(bind=conn) as session:
            with atomic_write(session):
                session.execute(text("SELECT 1"))
        dbapi.set_trace_callback(None)

    normalized_write = [s.upper() for s in write_statements]
    assert any("BEGIN IMMEDIATE" in s for s in normalized_write), (
        f"Write transaction did not execute BEGIN IMMEDIATE: {write_statements}"
    )

    engine.dispose()


def test_concurrent_issue_same_copy(tmp_path: Path):
    """
    Simulates concurrent attempts to issue the exact same book copy using atomic_write.
    Verifies that:
    1. Exactly ONE concurrent transaction successfully creates the active loan.
    2. The competing transaction is either serialized and rejected by business check
       or blocked and fails the unique partial index constraint (IntegrityError).
    3. Exactly one active loan exists for the copy in the database.
    """
    db_file = tmp_path / "concurrent_test.db"
    db_url = f"sqlite:///{db_file}"
    init_db(database_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    setup_engine_events(engine)

    # Seed initial entities
    with Session(engine) as session:
        with atomic_write(session):
            librarian = User(
                email="librarian@test.edu",
                hashed_password="hash",
                full_name="Test Librarian",
                role="librarian",
            )
            student1 = User(
                email="student1@test.edu",
                hashed_password="hash",
                full_name="Student One",
                role="student",
            )
            student2 = User(
                email="student2@test.edu",
                hashed_password="hash",
                full_name="Student Two",
                role="student",
            )
            book = Book(
                title="Concurrent Systems",
                author="Leslie Lamport",
                category="Computer Science",
            )
            session.add_all([librarian, student1, student2, book])
            session.flush()

            copy = BookCopy(
                book_id=book.id,
                copy_code="COPY-CONC-001",
                operational_status="available",
            )
            session.add(copy)
            session.flush()

            librarian_id = librarian.id
            student1_id = student1.id
            student2_id = student2.id
            copy_id = copy.id

    barrier = threading.Barrier(2)
    results = [None, None]

    def attempt_issue(thread_idx: int, student_id: int):
        barrier.wait()  # synchronize thread start
        with Session(engine) as session:
            try:
                with atomic_write(session):
                    # Check operational status and active loans
                    c = session.execute(
                        select(BookCopy).where(BookCopy.id == copy_id)
                    ).scalar_one_or_none()
                    if not c or c.operational_status != "available":
                        results[thread_idx] = ("rejected", "Copy not available")
                        return

                    existing_loan = session.execute(
                        select(Loan).where(Loan.copy_id == copy_id, Loan.returned_at.is_(None))
                    ).scalar_one_or_none()
                    if existing_loan:
                        results[thread_idx] = ("rejected", "Already loaned")
                        return

                    # Artificial micro-delay while holding the immediate write lock
                    time.sleep(0.05)

                    loan = Loan(
                        student_id=student_id,
                        copy_id=copy_id,
                        issued_by_id=librarian_id,
                        due_date=date.today() + timedelta(days=14),
                    )
                    session.add(loan)
                results[thread_idx] = ("success", student_id)
            except IntegrityError as exc:
                results[thread_idx] = ("integrity_error", str(exc))
            except OperationalError as exc:
                results[thread_idx] = ("locked_error", str(exc))

    t1 = threading.Thread(target=attempt_issue, args=(0, student1_id))
    t2 = threading.Thread(target=attempt_issue, args=(1, student2_id))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    statuses = [r[0] for r in results]
    assert "success" in statuses, f"Expected at least one success, got: {results}"
    assert statuses.count("success") == 1, (
        f"Expected exactly 1 successful issue, but got: {results}"
    )

    # Verify that in the database, exactly ONE active loan exists
    with Session(engine) as session:
        active_loans = session.execute(
            select(Loan).where(Loan.copy_id == copy_id, Loan.returned_at.is_(None))
        ).scalars().all()
        assert len(active_loans) == 1
        assert active_loans[0].student_id in (student1_id, student2_id)

    engine.dispose()


def test_foreign_keys_are_enforced(db):
    """
    Verifies that PRAGMA foreign_keys = ON is active and enforces referential integrity.
    Inserting a loan referencing non-existent copy_id and student_id must raise IntegrityError.
    """
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO loans (student_id, copy_id, issued_by_id, due_date) "
                "VALUES (99999, 99999, 99999, '2099-01-01');"
            )
        )
        db.flush()


def test_health_endpoint(client):
    """
    Verifies the health check endpoint returns 200 and confirms database connectivity.
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_atomic_write_rejects_existing_transaction(tmp_path: Path):
    """
    Verifies the transaction ownership rule: atomic_write() must NOT silently commit
    an existing deferred transaction to acquire a write lock. It must raise RuntimeError
    and leave the caller's transaction uncommitted.
    """
    db_file = tmp_path / "test_existing_txn.db"
    db_url = f"sqlite:///{db_file}"
    init_db(database_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    setup_engine_events(engine)

    with Session(engine) as session:
        # Start a deferred transaction by performing a query/mutation
        session.execute(text("SELECT 1;"))
        assert session.in_transaction() is True

        # Attempting to start atomic_write must reject with RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            with atomic_write(session):
                pass

        assert "already has an active transaction" in str(exc_info.value)
        # Ensure session did not silently commit
        session.rollback()

    engine.dispose()


def test_atomic_write_rollback_on_failure(tmp_path: Path):
    """
    Verifies that exceptions raised inside an atomic_write block cause a complete
    rollback and propagate the exception cleanly.
    """
    db_file = tmp_path / "test_rollback.db"
    db_url = f"sqlite:///{db_file}"
    init_db(database_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    setup_engine_events(engine)

    with Session(engine) as session:
        with pytest.raises(ValueError, match="Simulated mutation failure"):
            with atomic_write(session):
                user = User(
                    email="rollback_user@test.edu",
                    hashed_password="hash",
                    full_name="Rollback User",
                    role="student",
                )
                session.add(user)
                session.flush()
                raise ValueError("Simulated mutation failure")

    # Verify the user was NOT saved
    with Session(engine) as session:
        found = session.execute(
            select(User).where(User.email == "rollback_user@test.edu")
        ).scalar_one_or_none()
        assert found is None

    engine.dispose()


def test_atomic_write_nested_avoids_premature_commit(tmp_path: Path):
    """
    Verifies that nesting atomic_write blocks uses savepoints and avoids premature
    outer commits. If the outer block fails after inner success, all changes roll back.
    """
    db_file = tmp_path / "test_nested.db"
    db_url = f"sqlite:///{db_file}"
    init_db(database_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    setup_engine_events(engine)

    with Session(engine) as session:
        with pytest.raises(RuntimeError, match="Outer abort"):
            with atomic_write(session):
                u1 = User(
                    email="outer_user@test.edu",
                    hashed_password="hash",
                    full_name="Outer User",
                    role="student",
                )
                session.add(u1)
                session.flush()

                # Inner nested block
                with atomic_write(session):
                    u2 = User(
                        email="inner_user@test.edu",
                        hashed_password="hash",
                        full_name="Inner User",
                        role="student",
                    )
                    session.add(u2)
                    session.flush()

                # Outer block fails after inner completed
                raise RuntimeError("Outer abort")

    # Verify neither user was committed
    with Session(engine) as session:
        assert session.execute(
            select(User).where(User.email == "outer_user@test.edu")
        ).scalar_one_or_none() is None
        assert session.execute(
            select(User).where(User.email == "inner_user@test.edu")
        ).scalar_one_or_none() is None

    engine.dispose()


def test_get_write_db_cleanup_on_startup_failure(monkeypatch):
    """
    Verifies that if transaction startup fails inside get_write_db(),
    the session is cleanly rolled back, closed, and the exception propagates.
    """
    closed = False
    rolled_back = False

    class MockSession(Session):
        def connection(self, *args, **kwargs):
            raise OperationalError("BEGIN IMMEDIATE failed", params=None, orig=Exception("database locked"))
        def rollback(self):
            nonlocal rolled_back
            rolled_back = True
            super().rollback()
        def close(self):
            nonlocal closed
            closed = True
            super().close()

    mock_db = MockSession(create_engine("sqlite:///:memory:"))
    monkeypatch.setattr("app.database.SessionLocal", lambda: mock_db)

    gen = get_write_db()
    with pytest.raises(OperationalError, match="database locked"):
        next(gen)

    assert rolled_back is True
    assert closed is True
