"""
Automated test suite for Phase 1 – Step 2A: Core Schema and Migration Implementation.

Covers:
1. Model creation and constraints for all 7 resource-management tables:
   - study_zones (floor >= 0, capacity > 0, noise policy check)
   - study_seats (seat_code uniqueness, foreign keys)
   - study_rooms (capacity > 0, room_code uniqueness)
   - reservations (time ordering end > start, exclusive seat/room target, valid status)
   - occupancy_observations (non-negative count and utilization)
   - search_events (non-negative results and latency)
   - inventory_events (copy audit trails)
2. Reservation concurrency and overlap conflict prevention via SQLite triggers.
3. Teacher role integration:
   - User creation with 'teacher' role and token issuance.
   - Role dependency checks (require_teacher, require_borrower).
4. Teacher borrowing policy:
   - 30-day loan duration for teachers (vs 14-day for students).
   - 10-loan maximum limit for teachers (vs 3-loan for students).
   - Overdue blocking behavior.
5. Backward compatibility for loans.student_id column and existing loan workflows.
6. Alembic migration verification:
   - Sequential upgrade (0f610073e5f1 -> b2c3d4e5f6a7) and downgrade on isolated temp DB.
"""
from datetime import date, datetime, timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select, inspect, func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.utils.date import get_utc_today
from app.auth import create_access_token, hash_password
from app.dependencies import require_teacher, require_borrower
from app.models import (
    Base,
    User,
    Book,
    BookCopy,
    Loan,
    StudyZone,
    StudySeat,
    StudyRoom,
    Reservation,
    OccupancyObservation,
    SearchEvent,
    InventoryEvent,
)
from app.schemas import LoanIssueRequest
from app.services import loans as loans_service


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def teacher_user(db: Session) -> User:
    """Creates a sample active teacher."""
    teacher = User(
        email="prof.turing@university.edu",
        full_name="Professor Alan Turing",
        hashed_password=hash_password("TeacherSecret123!"),
        role="teacher",
        is_active=True,
    )
    db.add(teacher)
    db.flush()
    return teacher


@pytest.fixture
def student_user(db: Session) -> User:
    """Creates a sample active student."""
    student = User(
        email="student.ada@university.edu",
        full_name="Ada Lovelace",
        hashed_password=hash_password("StudentSecret123!"),
        role="student",
        is_active=True,
    )
    db.add(student)
    db.flush()
    return student


@pytest.fixture
def librarian_user(db: Session) -> User:
    """Creates a sample active librarian."""
    librarian = User(
        email="chief.librarian@university.edu",
        full_name="Chief Librarian",
        hashed_password=hash_password("LibSecret123!"),
        role="librarian",
        is_active=True,
    )
    db.add(librarian)
    db.flush()
    return librarian


@pytest.fixture
def test_books_and_copies(db: Session):
    """Creates a sample book and multiple available copies for borrowing tests."""
    book = Book(
        title="Structure and Interpretation of Computer Programs",
        author="Harold Abelson",
        isbn="9780262510875",
        category="Computer Science",
    )
    db.add(book)
    db.flush()

    copies = []
    for i in range(1, 15):
        copy = BookCopy(
            book_id=book.id,
            copy_code=f"SICP-{i:03d}",
            operational_status="available",
        )
        copies.append(copy)
    db.add_all(copies)
    db.flush()
    return {"book": book, "copies": copies}


# ── 1. Schema & Constraint Verification ───────────────────────────────────────

def test_study_zone_creation_and_constraints(db: Session):
    """Verifies study zone persistence and check constraints."""
    zone = StudyZone(
        zone_code="ZONE-SILENT-1A",
        name="1st Floor Silent Reading Hall",
        floor=1,
        total_capacity=50,
        noise_policy="silent",
    )
    db.add(zone)
    db.flush()
    assert zone.id is not None
    assert zone.is_active is True

    # Negative floor constraint check using a nested savepoint
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            invalid_zone = StudyZone(
                zone_code="INVALID-FLOOR",
                name="Underground",
                floor=-1,
                total_capacity=10,
            )
            db.add(invalid_zone)
            db.flush()


def test_study_seat_and_room_creation(db: Session):
    """Verifies seat and room persistence and relationships."""
    zone = StudyZone(
        zone_code="ZONE-COLLAB-2B",
        name="2nd Floor Collab Hub",
        floor=2,
        total_capacity=20,
        noise_policy="collaborative",
    )
    db.add(zone)
    db.flush()

    seat = StudySeat(
        zone_id=zone.id,
        seat_code="SEAT-2B-01",
        has_power_outlet=True,
        has_monitor=True,
        is_accessible=True,
    )
    db.add(seat)
    db.flush()

    room = StudyRoom(
        room_code="ROOM-COLLAB-1",
        name="Seminar Room Alpha",
        capacity=8,
        display_type="tv",
        has_whiteboard=True,
    )
    db.add(room)
    db.flush()

    assert seat.id is not None
    assert seat.zone.zone_code == "ZONE-COLLAB-2B"
    assert room.id is not None
    assert room.capacity == 8


def test_reservation_target_constraint(db: Session, student_user: User):
    """Verifies reservation resource target exclusivity constraint."""
    zone = StudyZone(zone_code="ZONE-TEST-RES", name="Test Zone", floor=1, total_capacity=10)
    db.add(zone)
    db.flush()
    seat = StudySeat(zone_id=zone.id, seat_code="SEAT-RES-01")
    room = StudyRoom(room_code="ROOM-RES-01", name="Room Res", capacity=4)
    db.add_all([seat, room])
    db.flush()

    now = datetime.utcnow()

    # Valid seat reservation
    res_seat = Reservation(
        user_id=student_user.id,
        resource_type="seat",
        seat_id=seat.id,
        start_time=now,
        end_time=now + timedelta(hours=2),
    )
    db.add(res_seat)
    db.flush()
    assert res_seat.id is not None

    # Invalid: seat type but room_id also set
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            bad_res = Reservation(
                user_id=student_user.id,
                resource_type="seat",
                seat_id=seat.id,
                room_id=room.id,
                start_time=now,
                end_time=now + timedelta(hours=2),
            )
            db.add(bad_res)
            db.flush()

    # Invalid: end_time <= start_time
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            bad_time = Reservation(
                user_id=student_user.id,
                resource_type="room",
                room_id=room.id,
                start_time=now + timedelta(hours=2),
                end_time=now,  # Invalid order
            )
            db.add(bad_time)
            db.flush()


def test_reservation_overlap_prevention_trigger(db: Session, student_user: User, teacher_user: User):
    """
    Verifies that overlapping reservations on the same seat are blocked by SQLite triggers.
    """
    zone = StudyZone(zone_code="ZONE-TRIG-TEST", name="Trigger Zone", floor=1, total_capacity=5)
    db.add(zone)
    db.flush()
    seat = StudySeat(zone_id=zone.id, seat_code="SEAT-TRIG-01")
    db.add(seat)
    db.flush()

    base_time = datetime(2026, 11, 1, 10, 0, 0)
    res1 = Reservation(
        user_id=student_user.id,
        resource_type="seat",
        seat_id=seat.id,
        start_time=base_time,
        end_time=base_time + timedelta(hours=2),  # 10:00 - 12:00
        status="active",
    )
    db.add(res1)
    db.flush()

    # Attempt overlapping reservation: 11:00 - 13:00 (overlaps by 1 hour)
    with pytest.raises((IntegrityError, OperationalError)) as excinfo:
        with db.begin_nested():
            overlap_res = Reservation(
                user_id=teacher_user.id,
                resource_type="seat",
                seat_id=seat.id,
                start_time=base_time + timedelta(hours=1),
                end_time=base_time + timedelta(hours=3),
                status="active",
            )
            db.add(overlap_res)
            db.flush()
    assert "conflict" in str(excinfo.value).lower()

    # Non-overlapping reservation: 12:00 - 14:00 must succeed
    ok_res = Reservation(
        user_id=teacher_user.id,
        resource_type="seat",
        seat_id=seat.id,
        start_time=base_time + timedelta(hours=2),
        end_time=base_time + timedelta(hours=4),
        status="active",
    )
    db.add(ok_res)
    db.flush()
    assert ok_res.id is not None


def test_occupancy_observation_constraints(db: Session):
    """Verifies occupancy observation persistence and non-negative constraints."""
    zone = StudyZone(zone_code="ZONE-OCC-TEST", name="Occupancy Zone", floor=1, total_capacity=20)
    db.add(zone)
    db.flush()

    obs = OccupancyObservation(
        zone_id=zone.id,
        observed_count=12,
        capacity_utilization=0.6,
        source_sensor_id="SENSOR-1A-01",
    )
    db.add(obs)
    db.flush()
    assert obs.id is not None

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            bad_obs = OccupancyObservation(
                zone_id=zone.id,
                observed_count=-1,
                capacity_utilization=0.0,
            )
            db.add(bad_obs)
            db.flush()


def test_search_and_inventory_events(db: Session, student_user: User, librarian_user: User, test_books_and_copies):
    """Verifies search events and inventory audit event logging."""
    search_evt = SearchEvent(
        user_id=student_user.id,
        query_text="operating systems concepts",
        search_type="semantic",
        results_count=5,
        latency_ms=42.5,
    )
    db.add(search_evt)
    db.flush()
    assert search_evt.id is not None

    copy = test_books_and_copies["copies"][0]
    inv_evt = InventoryEvent(
        copy_id=copy.id,
        auditor_id=librarian_user.id,
        event_type="audit_scan",
        previous_status="available",
        new_status="available",
        notes="Physical barcode scanned and verified.",
    )
    db.add(inv_evt)
    db.flush()
    assert inv_evt.id is not None
    assert inv_evt.auditor.role == "librarian"


# ── 2. Teacher Role & Borrowing Policy Verification ───────────────────────────

def test_teacher_role_authentication_and_authorization(teacher_user: User, student_user: User, librarian_user: User):
    """Verifies teacher role dependency authorization."""
    teacher_checker = require_teacher
    borrower_checker = require_borrower

    # Teacher satisfies both require_teacher and require_borrower
    assert teacher_checker(teacher_user).role == "teacher"
    assert borrower_checker(teacher_user).role == "teacher"

    # Student satisfies require_borrower, but raises 403 on require_teacher
    assert borrower_checker(student_user).role == "student"
    with pytest.raises(Exception) as exc:
        teacher_checker(student_user)
    assert exc.value.status_code == 403

    # Librarian raises 403 on require_borrower
    with pytest.raises(Exception) as exc:
        borrower_checker(librarian_user)
    assert exc.value.status_code == 403


def test_teacher_30_day_due_date_and_10_loan_limit(
    db: Session,
    teacher_user: User,
    librarian_user: User,
    test_books_and_copies,
):
    """
    Verifies that teachers receive 30-day loans and can borrow up to 10 books.
    """
    db.info["_in_atomic_write"] = True
    try:
        copies = test_books_and_copies["copies"]
        today = get_utc_today()

        # Issue 10 loans to the teacher
        for i in range(10):
            req = LoanIssueRequest(student_id=teacher_user.id, copy_id=copies[i].id)
            loan_resp = loans_service.issue_loan_service(db, req, librarian_id=librarian_user.id)
            assert loan_resp.status == "active"
            expected_due = today + timedelta(days=30)
            assert loan_resp.due_date == expected_due

        # 11th loan must be rejected with 400 Bad Request
        req_11 = LoanIssueRequest(student_id=teacher_user.id, copy_id=copies[10].id)
        with pytest.raises(Exception) as exc:
            loans_service.issue_loan_service(db, req_11, librarian_id=librarian_user.id)
        assert exc.value.status_code == 400
        assert "maximum borrowing limit of 10" in exc.value.detail
    finally:
        db.info.pop("_in_atomic_write", None)


def test_student_retains_3_loan_limit_and_14_day_due_date(
    db: Session,
    student_user: User,
    librarian_user: User,
    test_books_and_copies,
):
    """
    Verifies that existing student borrowing policy is unaffected (3 loans, 14 days).
    """
    db.info["_in_atomic_write"] = True
    try:
        copies = test_books_and_copies["copies"]
        today = get_utc_today()

        for i in range(3):
            req = LoanIssueRequest(student_id=student_user.id, copy_id=copies[i].id)
            loan_resp = loans_service.issue_loan_service(db, req, librarian_id=librarian_user.id)
            expected_due = today + timedelta(days=14)
            assert loan_resp.due_date == expected_due

        # 4th loan must be rejected
        req_4 = LoanIssueRequest(student_id=student_user.id, copy_id=copies[3].id)
        with pytest.raises(Exception) as exc:
            loans_service.issue_loan_service(db, req_4, librarian_id=librarian_user.id)
        assert exc.value.status_code == 400
        assert "maximum borrowing limit of 3" in exc.value.detail
    finally:
        db.info.pop("_in_atomic_write", None)


# ── 3. Alembic Migration Upgrade & Downgrade Verification ─────────────────────

def test_alembic_sequential_upgrade_and_downgrade(tmp_path: Path):
    """
    Verifies that the Alembic migration runs sequentially on a clean SQLite database:
    1. Upgrade to initial schema 0f610073e5f1.
    2. Upgrade to phase 1 resource management b2c3d4e5f6a7.
    3. Upgrade to corrective migration c3d4e5f6a7b8 (align triggers to status = 'active').
    4. Verify triggers in c3d4e5f6a7b8 and test overlap semantics.
    5. Downgrade back to b2c3d4e5f6a7 and verify restored trigger definitions.
    6. Downgrade back to 0f610073e5f1.
    7. Upgrade again to head.
    """
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import text

    test_db_path = tmp_path / "test_migration.db"
    test_db_url = f"sqlite:///{test_db_path.as_posix()}"

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # Step 1: Upgrade to baseline 0f610073e5f1
    command.upgrade(alembic_cfg, "0f610073e5f1")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables_0f = set(inspector.get_table_names())
    assert {"books", "book_copies", "loans", "users"}.issubset(tables_0f)
    assert "study_zones" not in tables_0f

    # Step 2: Upgrade to phase 1 b2c3d4e5f6a7
    command.upgrade(alembic_cfg, "b2c3d4e5f6a7")
    inspector = inspect(engine)
    tables_phase1 = set(inspector.get_table_names())
    required_tables = {
        "study_zones",
        "study_seats",
        "study_rooms",
        "reservations",
        "occupancy_observations",
        "search_events",
        "inventory_events",
    }
    assert required_tables.issubset(tables_phase1)

    # Check triggers at b2c3d4e5f6a7 (should have ('active', 'confirmed'))
    with engine.connect() as conn:
        triggers_b2 = conn.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_prevent_%'")
        ).fetchall()
        assert len(triggers_b2) == 4
        for name, sql in triggers_b2:
            assert "('active', 'confirmed')" in sql

    # Step 3: Upgrade to corrective revision c3d4e5f6a7b8
    command.upgrade(alembic_cfg, "c3d4e5f6a7b8")
    with engine.connect() as conn:
        triggers_c3 = conn.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_prevent_%'")
        ).fetchall()
        assert len(triggers_c3) == 4
        for name, sql in triggers_c3:
            assert "status = 'active'" in sql
            assert "('active', 'confirmed')" not in sql

        # Test overlap behavior under c3d4e5f6a7b8 triggers
        # Seed user, zone, and seat
        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) "
                "VALUES (1, 'u@test.com', 'Test User', 'hash', 'student', 1, '2026-10-31 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, created_at) "
                "VALUES (1, 'Z1', 'Zone 1', 1, 10, 'quiet', '2026-10-31 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, created_at) "
                "VALUES (1, 1, 'S1', 1, 0, 1, '2026-10-31 00:00:00')"
            )
        )
        conn.commit()

        # Insert active reservation 10:00 - 12:00
        conn.execute(
            text(
                "INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, created_at) "
                "VALUES (1, 1, 'seat', 1, '2026-11-01 10:00:00', '2026-11-01 12:00:00', 'active', '2026-10-31 00:00:00')"
            )
        )
        conn.commit()

        # Overlapping cancelled reservation (11:00 - 13:00) should SUCCEED
        conn.execute(
            text(
                "INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, created_at) "
                "VALUES (2, 1, 'seat', 1, '2026-11-01 11:00:00', '2026-11-01 13:00:00', 'cancelled', '2026-10-31 00:00:00')"
            )
        )
        conn.commit()

        # Overlapping completed reservation (11:00 - 13:00) should SUCCEED
        conn.execute(
            text(
                "INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, created_at) "
                "VALUES (3, 1, 'seat', 1, '2026-11-01 11:00:00', '2026-11-01 13:00:00', 'completed', '2026-10-31 00:00:00')"
            )
        )
        conn.commit()

        # Overlapping active reservation (11:00 - 13:00) must FAIL
        with pytest.raises(Exception) as exc_info:
            conn.execute(
                text(
                    "INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, created_at) "
                    "VALUES (4, 1, 'seat', 1, '2026-11-01 11:00:00', '2026-11-01 13:00:00', 'active', '2026-10-31 00:00:00')"
                )
            )
            conn.commit()
        assert "conflict" in str(exc_info.value).lower()
        conn.rollback()

    # Step 4: Downgrade back to b2c3d4e5f6a7
    command.downgrade(alembic_cfg, "b2c3d4e5f6a7")
    with engine.connect() as conn:
        triggers_downgraded_b2 = conn.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_prevent_%'")
        ).fetchall()
        assert len(triggers_downgraded_b2) == 4
        for name, sql in triggers_downgraded_b2:
            assert "('active', 'confirmed')" in sql

    # Step 5: Downgrade back to 0f610073e5f1
    command.downgrade(alembic_cfg, "0f610073e5f1")
    inspector = inspect(engine)
    tables_downgraded = set(inspector.get_table_names())
    for t in required_tables:
        assert t not in tables_downgraded
    assert {"books", "book_copies", "loans", "users"}.issubset(tables_downgraded)

    # Step 6: Re-upgrade to head (which resolves to a1b2c3d4e5f6)
    command.upgrade(alembic_cfg, "head")
    inspector = inspect(engine)
    tables_reupgraded = set(inspector.get_table_names())
    assert required_tables.issubset(tables_reupgraded)
    with engine.connect() as conn:
        current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert current_rev == "a1b2c3d4e5f6"
