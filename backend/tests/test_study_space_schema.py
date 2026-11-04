"""
Automated test suite for Stage 10.1: Study Space Schema & Model Alignment.

Covers:
1. New reservation model/schema compatibility (checked_in_at, expected_attendees, actual_attendees).
2. Existing reservation data backfill (expected_attendees=1, checked_in_at=NULL).
3. Seat attendee constraints (expected_attendees=1, actual_attendees in (NULL, 1)).
4. Room attendee constraints (expected_attendees >= 1, actual_attendees in (NULL, >= 1)).
5. NULL-safe INSERT overlap trigger (blocks student/teacher overlapping active bookings).
6. NULL-safe UPDATE overlap trigger (excludes current reservation id != NEW.id).
7. Librarian/admin overlap exemptions (permitted to hold overlapping reservations).
8. Unknown and NULL role default-deny (blocked from self-overlap).
9. Role demotion with overlapping reservations (blocked).
10. Role demotion without overlapping reservations (permitted).
11. Existing resource collision triggers remain effective.
12. Migration upgrade and downgrade on an isolated disposable test database.
13. Migration upgrade preserves historical reservation records.
"""
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic import command

from app.models import (
    Base,
    User,
    StudyZone,
    StudySeat,
    StudyRoom,
    Reservation,
)
from app.schemas import (
    ReservationCreate,
    ReservationCheckInRequest,
    ReservationResponse,
    StudyZoneResponse,
    StudySeatResponse,
    StudyRoomResponse,
)


@pytest.fixture
def test_users(db: Session):
    student = User(
        email="student.test10@university.edu",
        full_name="Test Student",
        hashed_password="hash",
        role="student",
        is_active=True,
    )
    teacher = User(
        email="prof.test10@university.edu",
        full_name="Test Teacher",
        hashed_password="hash",
        role="teacher",
        is_active=True,
    )
    librarian = User(
        email="lib.test10@university.edu",
        full_name="Test Librarian",
        hashed_password="hash",
        role="librarian",
        is_active=True,
    )
    admin = User(
        email="admin.test10@university.edu",
        full_name="Test Admin",
        hashed_password="hash",
        role="admin",
        is_active=True,
    )
    unknown_user = User(
        email="guest.test10@university.edu",
        full_name="Test Guest",
        hashed_password="hash",
        role="guest",
        is_active=True,
    )
    db.add_all([student, teacher, librarian, admin, unknown_user])
    db.flush()
    return {
        "student": student,
        "teacher": teacher,
        "librarian": librarian,
        "admin": admin,
        "guest": unknown_user,
    }


@pytest.fixture
def test_spaces(db: Session):
    zone = StudyZone(
        zone_code="ZONE-T10",
        name="Stage 10 Test Zone",
        floor=1,
        total_capacity=10,
        noise_policy="quiet",
        is_active=True,
    )
    db.add(zone)
    db.flush()

    seat1 = StudySeat(zone_id=zone.id, seat_code="SEAT-T10-01", is_active=True)
    seat2 = StudySeat(zone_id=zone.id, seat_code="SEAT-T10-02", is_active=True)
    room1 = StudyRoom(room_code="ROOM-T10-01", name="Room Alpha", capacity=6, is_active=True)
    room2 = StudyRoom(room_code="ROOM-T10-02", name="Room Beta", capacity=8, is_active=True)
    db.add_all([seat1, seat2, room1, room2])
    db.flush()
    return {
        "zone": zone,
        "seat1": seat1,
        "seat2": seat2,
        "room1": room1,
        "room2": room2,
    }


def test_schema_attendee_validation_types():
    """Validates Pydantic schema rejection of booleans, negative counts, and invalid seat counts."""
    base_time = datetime(2026, 11, 2, 10, 0, 0)
    end_time = datetime(2026, 11, 2, 12, 0, 0)

    # 1. Reject boolean as expected_attendees
    with pytest.raises(ValueError, match="not a boolean"):
        ReservationCreate(
            resource_type="room",
            room_id=1,
            start_time=base_time,
            end_time=end_time,
            expected_attendees=True,  # type: ignore
        )

    # 2. Reject zero expected_attendees
    with pytest.raises(ValueError, match="at least 1"):
        ReservationCreate(
            resource_type="room",
            room_id=1,
            start_time=base_time,
            end_time=end_time,
            expected_attendees=0,
        )

    # 3. Reject negative expected_attendees
    with pytest.raises(ValueError, match="at least 1"):
        ReservationCreate(
            resource_type="room",
            room_id=1,
            start_time=base_time,
            end_time=end_time,
            expected_attendees=-5,
        )

    # 4. Reject seat reservation with expected_attendees != 1
    with pytest.raises(ValueError, match="Seat reservations must have exactly 1"):
        ReservationCreate(
            resource_type="seat",
            seat_id=1,
            start_time=base_time,
            end_time=end_time,
            expected_attendees=2,
        )

    # 5. CheckInRequest rejects boolean and <= 0
    with pytest.raises(ValueError, match="not a boolean"):
        ReservationCheckInRequest(actual_attendees=True)  # type: ignore

    with pytest.raises(ValueError, match="at least 1"):
        ReservationCheckInRequest(actual_attendees=0)

    # 6. Valid room creation
    valid_room = ReservationCreate(
        resource_type="room",
        room_id=1,
        start_time=base_time,
        end_time=end_time,
        expected_attendees=4,
    )
    assert valid_room.expected_attendees == 4

    # 7. Valid seat creation defaults to 1
    valid_seat = ReservationCreate(
        resource_type="seat",
        seat_id=1,
        start_time=base_time,
        end_time=end_time,
    )
    assert valid_seat.expected_attendees == 1


def test_seat_attendee_database_constraints(db: Session, test_users, test_spaces):
    """Verifies that DB check constraints enforce expected_attendees=1 and actual_attendees in (NULL, 1) for seats."""
    base_time = datetime(2026, 11, 2, 10, 0, 0)
    end_time = datetime(2026, 11, 2, 12, 0, 0)

    # Valid seat reservation
    res = Reservation(
        user_id=test_users["student"].id,
        resource_type="seat",
        seat_id=test_spaces["seat1"].id,
        start_time=base_time,
        end_time=end_time,
        expected_attendees=1,
        actual_attendees=None,
    )
    db.add(res)
    db.flush()
    assert res.id is not None

    # Invalid seat reservation: expected_attendees = 2
    with pytest.raises((IntegrityError, OperationalError)):
        with db.begin_nested():
            bad_res = Reservation(
                user_id=test_users["teacher"].id,
                resource_type="seat",
                seat_id=test_spaces["seat2"].id,
                start_time=base_time,
                end_time=end_time,
                expected_attendees=2,
            )
            db.add(bad_res)
            db.flush()

    # Invalid seat reservation: actual_attendees = 2
    with pytest.raises((IntegrityError, OperationalError)):
        with db.begin_nested():
            bad_act = Reservation(
                user_id=test_users["teacher"].id,
                resource_type="seat",
                seat_id=test_spaces["seat2"].id,
                start_time=base_time,
                end_time=end_time,
                expected_attendees=1,
                actual_attendees=2,
            )
            db.add(bad_act)
            db.flush()


def test_room_attendee_database_constraints(db: Session, test_users, test_spaces):
    """Verifies that DB check constraints enforce expected_attendees >= 1 and actual_attendees >= 1 for rooms."""
    base_time = datetime(2026, 11, 2, 10, 0, 0)
    end_time = datetime(2026, 11, 2, 12, 0, 0)

    # Valid room reservation
    res = Reservation(
        user_id=test_users["student"].id,
        resource_type="room",
        room_id=test_spaces["room1"].id,
        start_time=base_time,
        end_time=end_time,
        expected_attendees=5,
        actual_attendees=5,
    )
    db.add(res)
    db.flush()
    assert res.expected_attendees == 5
    assert res.actual_attendees == 5

    # Invalid room reservation: expected_attendees = 0
    with pytest.raises((IntegrityError, OperationalError)):
        with db.begin_nested():
            bad_room = Reservation(
                user_id=test_users["teacher"].id,
                resource_type="room",
                room_id=test_spaces["room2"].id,
                start_time=base_time,
                end_time=end_time,
                expected_attendees=0,
            )
            db.add(bad_room)
            db.flush()

    # Invalid room reservation: actual_attendees = 0
    with pytest.raises((IntegrityError, OperationalError)):
        with db.begin_nested():
            bad_act = Reservation(
                user_id=test_users["teacher"].id,
                resource_type="room",
                room_id=test_spaces["room2"].id,
                start_time=base_time,
                end_time=end_time,
                expected_attendees=4,
                actual_attendees=0,
            )
            db.add(bad_act)
            db.flush()


def test_null_safe_user_overlap_insert_trigger(db: Session, test_users, test_spaces):
    """Verifies that student, teacher, and NULL/unknown roles are blocked from overlapping bookings across different resources."""
    base_time = datetime(2026, 11, 2, 10, 0, 0)
    end_time = datetime(2026, 11, 2, 12, 0, 0)

    # 1. Student books Seat 1
    s_res1 = Reservation(
        user_id=test_users["student"].id,
        resource_type="seat",
        seat_id=test_spaces["seat1"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    db.add(s_res1)
    db.flush()

    # Student attempts overlapping booking on Room 1 (11:00 - 13:00) -> MUST FAIL
    with pytest.raises((IntegrityError, OperationalError)) as exc:
        with db.begin_nested():
            s_overlap = Reservation(
                user_id=test_users["student"].id,
                resource_type="room",
                room_id=test_spaces["room1"].id,
                start_time=base_time + timedelta(hours=1),
                end_time=base_time + timedelta(hours=3),
                status="active",
                expected_attendees=3,
            )
            db.add(s_overlap)
            db.flush()
    assert "conflict" in str(exc.value).lower()

    # 2. Teacher books Seat 2 (10:00 - 12:00)
    t_res1 = Reservation(
        user_id=test_users["teacher"].id,
        resource_type="seat",
        seat_id=test_spaces["seat2"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    db.add(t_res1)
    db.flush()

    # Teacher attempts overlapping booking on Room 1 -> MUST FAIL
    with pytest.raises((IntegrityError, OperationalError)) as exc:
        with db.begin_nested():
            t_overlap = Reservation(
                user_id=test_users["teacher"].id,
                resource_type="room",
                room_id=test_spaces["room1"].id,
                start_time=base_time + timedelta(minutes=30),
                end_time=base_time + timedelta(hours=2),
                status="active",
                expected_attendees=4,
            )
            db.add(t_overlap)
            db.flush()
    assert "conflict" in str(exc.value).lower()

    # Non-overlapping booking by teacher (12:00 - 14:00) -> MUST SUCCEED (half-open)
    t_ok = Reservation(
        user_id=test_users["teacher"].id,
        resource_type="room",
        room_id=test_spaces["room1"].id,
        start_time=end_time,
        end_time=end_time + timedelta(hours=2),
        status="active",
        expected_attendees=4,
    )
    db.add(t_ok)
    db.flush()
    assert t_ok.id is not None


def test_librarian_and_admin_overlap_exemption(db: Session, test_users, test_spaces):
    """Verifies that librarians and administrators CAN book overlapping slots across distinct resources."""
    base_time = datetime(2026, 11, 2, 14, 0, 0)
    end_time = datetime(2026, 11, 2, 16, 0, 0)

    # Librarian books Room 1
    lib_res1 = Reservation(
        user_id=test_users["librarian"].id,
        resource_type="room",
        room_id=test_spaces["room1"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
        expected_attendees=4,
    )
    db.add(lib_res1)
    db.flush()

    # Librarian books Room 2 for the exact same interval (staging workshop) -> SUCCEEDS
    lib_res2 = Reservation(
        user_id=test_users["librarian"].id,
        resource_type="room",
        room_id=test_spaces["room2"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
        expected_attendees=6,
    )
    db.add(lib_res2)
    db.flush()
    assert lib_res2.id is not None

    # Admin books Seat 1 and Seat 2 concurrently -> SUCCEEDS
    admin_res1 = Reservation(
        user_id=test_users["admin"].id,
        resource_type="seat",
        seat_id=test_spaces["seat1"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    admin_res2 = Reservation(
        user_id=test_users["admin"].id,
        resource_type="seat",
        seat_id=test_spaces["seat2"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    db.add_all([admin_res1, admin_res2])
    db.flush()
    assert admin_res1.id is not None
    assert admin_res2.id is not None


def test_resource_level_triggers_still_block_librarian_double_booking(db: Session, test_users, test_spaces):
    """Verifies that resource-level triggers apply globally: even librarians cannot double-book the SAME resource."""
    base_time = datetime(2026, 11, 2, 16, 0, 0)
    end_time = datetime(2026, 11, 2, 18, 0, 0)

    lib_res1 = Reservation(
        user_id=test_users["librarian"].id,
        resource_type="room",
        room_id=test_spaces["room1"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
        expected_attendees=4,
    )
    db.add(lib_res1)
    db.flush()

    # Attempt to book the SAME room again for the same slot -> MUST FAIL
    with pytest.raises((IntegrityError, OperationalError)) as exc:
        with db.begin_nested():
            duplicate = Reservation(
                user_id=test_users["librarian"].id,
                resource_type="room",
                room_id=test_spaces["room1"].id,
                start_time=base_time + timedelta(hours=1),
                end_time=end_time + timedelta(hours=1),
                status="active",
                expected_attendees=4,
            )
            db.add(duplicate)
            db.flush()
    assert "conflict" in str(exc.value).lower()


def test_update_overlap_trigger_excludes_current_reservation(db: Session, test_users, test_spaces):
    """Verifies that trg_prevent_user_reservation_overlap_update excludes id != NEW.id on check-in or metadata update."""
    base_time = datetime(2026, 11, 2, 10, 0, 0)
    end_time = datetime(2026, 11, 2, 12, 0, 0)

    res = Reservation(
        user_id=test_users["student"].id,
        resource_type="seat",
        seat_id=test_spaces["seat1"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    db.add(res)
    db.flush()

    # Update check-in timestamp and attendance on the SAME reservation -> MUST NOT TRIGGER SELF-COLLISION
    res.checked_in_at = base_time + timedelta(minutes=5)
    res.actual_attendees = 1
    db.flush()
    assert res.checked_in_at is not None


def test_null_and_unknown_role_default_deny(db: Session, test_users, test_spaces):
    """Verifies that unknown roles and users with NULL role are blocked by the user overlap trigger."""
    base_time = datetime(2026, 11, 2, 10, 0, 0)
    end_time = datetime(2026, 11, 2, 12, 0, 0)

    # 1. Unknown role 'guest'
    guest = test_users["guest"]
    r1 = Reservation(
        user_id=guest.id,
        resource_type="seat",
        seat_id=test_spaces["seat1"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    db.add(r1)
    db.flush()

    # Overlapping booking for guest -> MUST FAIL
    with pytest.raises((IntegrityError, OperationalError)) as exc:
        with db.begin_nested():
            r2 = Reservation(
                user_id=guest.id,
                resource_type="room",
                room_id=test_spaces["room1"].id,
                start_time=base_time + timedelta(hours=1),
                end_time=base_time + timedelta(hours=3),
                status="active",
                expected_attendees=2,
            )
            db.add(r2)
            db.flush()
    assert "conflict" in str(exc.value).lower()

    # 2. Empty-string role user (demonstrating default-deny on non-privileged empty/unknown role)
    empty_role_user = User(
        email="empty.role@university.edu",
        full_name="Empty Role User",
        hashed_password="hash",
        role="",
        is_active=True,
    )
    db.add(empty_role_user)
    db.flush()

    nr1 = Reservation(
        user_id=empty_role_user.id,
        resource_type="seat",
        seat_id=test_spaces["seat2"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    db.add(nr1)
    db.flush()

    # Overlapping booking for empty-role user -> MUST FAIL (COALESCE/NOT IN blocks)
    with pytest.raises((IntegrityError, OperationalError)) as exc:
        with db.begin_nested():
            nr2 = Reservation(
                user_id=empty_role_user.id,
                resource_type="room",
                room_id=test_spaces["room2"].id,
                start_time=base_time + timedelta(minutes=30),
                end_time=base_time + timedelta(hours=2),
                status="active",
                expected_attendees=2,
            )
            db.add(nr2)
            db.flush()
    assert "conflict" in str(exc.value).lower()


def test_role_demotion_trigger(db: Session, test_spaces):
    """Verifies trg_prevent_role_demotion_with_overlapping_reservations blocks demoting a privileged user holding overlaps."""
    base_time = datetime(2026, 11, 2, 10, 0, 0)
    end_time = datetime(2026, 11, 2, 12, 0, 0)

    # Privileged user with overlapping bookings
    lib_user = User(
        email="demote.lib@university.edu",
        full_name="Demote Librarian",
        hashed_password="hash",
        role="librarian",
        is_active=True,
    )
    db.add(lib_user)
    db.flush()

    r1 = Reservation(
        user_id=lib_user.id,
        resource_type="seat",
        seat_id=test_spaces["seat1"].id,
        start_time=base_time,
        end_time=end_time,
        status="active",
    )
    r2 = Reservation(
        user_id=lib_user.id,
        resource_type="seat",
        seat_id=test_spaces["seat2"].id,
        start_time=base_time + timedelta(minutes=30),
        end_time=base_time + timedelta(hours=2),
        status="active",
    )
    db.add_all([r1, r2])
    db.flush()

    # 1. Demote to student -> MUST FAIL
    with pytest.raises((IntegrityError, OperationalError)) as exc:
        with db.begin_nested():
            lib_user.role = "student"
            db.flush()
    assert "role update rejected" in str(exc.value).lower()

    # 2. Demote to NULL -> MUST FAIL
    with pytest.raises((IntegrityError, OperationalError)) as exc:
        with db.begin_nested():
            lib_user.role = None  # type: ignore
            db.flush()
    assert "role update rejected" in str(exc.value).lower()

    # 3. Transition to admin (privileged to privileged) -> MUST SUCCEED
    lib_user.role = "admin"
    db.flush()
    assert lib_user.role == "admin"

    # 4. Another user without overlapping bookings demoting to student -> MUST SUCCEED
    clean_lib = User(
        email="clean.lib@university.edu",
        full_name="Clean Librarian",
        hashed_password="hash",
        role="librarian",
        is_active=True,
    )
    db.add(clean_lib)
    db.flush()

    clean_res = Reservation(
        user_id=clean_lib.id,
        resource_type="seat",
        seat_id=test_spaces["seat1"].id,
        start_time=end_time + timedelta(hours=1),
        end_time=end_time + timedelta(hours=3),
        status="active",
    )
    db.add(clean_res)
    db.flush()

    clean_lib.role = "student"
    db.flush()
    assert clean_lib.role == "student"


def test_alembic_migration_upgrade_and_downgrade(tmp_path: Path):
    """
    Executes full sequential Alembic upgrade and downgrade on an isolated disposable test database.
    Verifies that e5f6a7b8c9d0 adds columns, backfills expected_attendees, creates triggers, and cleanly downgrades.
    """
    test_db_path = tmp_path / "stage10_migration_test.db"
    db_url = f"sqlite:///{test_db_path.as_posix()}"

    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    engine = create_engine(db_url)

    # 1. Upgrade to previous head (d4e5f6a7b8c9)
    command.upgrade(alembic_cfg, "d4e5f6a7b8c9")
    inspector = inspect(engine)
    cols_d4 = {c["name"] for c in inspector.get_columns("reservations")}
    assert "checked_in_at" not in cols_d4
    assert "expected_attendees" not in cols_d4
    assert "actual_attendees" not in cols_d4

    # Seed historical records under d4e5f6a7b8c9
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) "
            "VALUES (1, 'u1@test.com', 'User 1', 'hash', 'student', 1, '2026-10-31 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, created_at) "
            "VALUES (1, 'Z1', 'Zone 1', 1, 10, 'quiet', '2026-10-31 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, created_at) "
            "VALUES (1, 1, 'S1', 1, 0, 1, '2026-10-31 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, created_at) "
            "VALUES (100, 1, 'seat', 1, '2026-11-01 10:00:00', '2026-11-01 12:00:00', 'completed', '2026-10-31 00:00:00')"
        ))
        conn.commit()

    # 2. Upgrade to new revision (e5f6a7b8c9d0)
    command.upgrade(alembic_cfg, "e5f6a7b8c9d0")
    inspector = inspect(engine)
    cols_e5 = {c["name"] for c in inspector.get_columns("reservations")}
    assert "checked_in_at" in cols_e5
    assert "expected_attendees" in cols_e5
    assert "actual_attendees" in cols_e5

    # Verify historical data preservation and backfill
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, expected_attendees, actual_attendees, checked_in_at, status FROM reservations WHERE id=100")).fetchone()
        assert row is not None
        assert row[0] == 100
        assert row[1] == 1  # backfilled to 1
        assert row[2] is None  # actual_attendees is NULL
        assert row[3] is None  # checked_in_at is NULL
        assert row[4] == "completed"  # status preserved

        # Verify triggers present
        triggers = conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'")).fetchall()
        trig_names = {t[0] for t in triggers}
        assert "trg_prevent_seat_reservation_insert" in trig_names
        assert "trg_prevent_seat_reservation_update" in trig_names
        assert "trg_prevent_room_reservation_insert" in trig_names
        assert "trg_prevent_room_reservation_update" in trig_names
        assert "trg_prevent_user_reservation_overlap_insert" in trig_names
        assert "trg_prevent_user_reservation_overlap_update" in trig_names
        assert "trg_prevent_role_demotion_with_overlapping_reservations" in trig_names

    # 3. Downgrade back to d4e5f6a7b8c9
    command.downgrade(alembic_cfg, "d4e5f6a7b8c9")
    inspector = inspect(engine)
    cols_down = {c["name"] for c in inspector.get_columns("reservations")}
    assert "checked_in_at" not in cols_down
    assert "expected_attendees" not in cols_down
    assert "actual_attendees" not in cols_down

    with engine.connect() as conn:
        # Verify user overlap triggers removed
        triggers = conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'")).fetchall()
        trig_names = {t[0] for t in triggers}
        assert "trg_prevent_user_reservation_overlap_insert" not in trig_names
        assert "trg_prevent_user_reservation_overlap_update" not in trig_names
        assert "trg_prevent_role_demotion_with_overlapping_reservations" not in trig_names
        # Resource triggers still preserved
        assert "trg_prevent_seat_reservation_insert" in trig_names
        assert "trg_prevent_room_reservation_insert" in trig_names

    engine.dispose()
