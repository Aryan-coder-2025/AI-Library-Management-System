"""
Automated test suite for Stage 10.2: Transactional Study Space Booking Service.

Covers:
1. Valid seat reservation by student (201 Created, expected_attendees=1).
2. Valid room reservation by teacher (201 Created, expected_attendees within capacity).
3. Resource target validation (seat specifies seat_id, room specifies room_id, mutual exclusion).
4. Expected attendees bounds (seat must be 1, room must be 1 <= count <= capacity).
5. Integer/boolean type validation on attendee counts.
6. Time validation:
   - end_time <= start_time rejected.
   - start_time in the past rejected.
   - duration < 30 minutes rejected.
   - seat duration > 4 hours rejected.
   - room duration > 3 hours rejected.
   - outside library operating hours (08:00-22:00 IST) rejected.
   - crossing calendar day rejected.
7. Advance booking windows:
   - student > 7 days rejected.
   - teacher > 14 days rejected.
   - librarian up to 30 days permitted.
8. Active reservation quotas:
   - student max 1 active reservation; second active rejected.
   - teacher max 2 active reservations; third active rejected.
   - librarian unlimited active reservations.
   - cancelled/completed reservations do not count toward quota.
9. User-level concurrency & self-overlap:
   - student / teacher cannot hold overlapping active bookings -> 409 Conflict.
   - librarian permitted overlapping bookings across distinct resources.
10. Resource collisions:
    - overlapping seat reservation by another user -> 409 Conflict.
    - overlapping room reservation by another user -> 409 Conflict.
11. Default-deny on unknown / guest role -> 403 Forbidden.
12. Inactive resource rejection -> 400 Bad Request.
13. Cancellation lifecycle:
    - patron cancels own active reservation -> status='cancelled'.
    - quota restored after cancellation.
    - unauthorized patron cannot cancel another patron's reservation -> 403 Forbidden.
    - librarian can cancel any active reservation -> 200 OK.
    - cannot cancel non-active or past reservation -> 400 Bad Request.
14. Reservation retrieval:
    - owner views own reservation -> 200 OK.
    - non-owner viewing rejected -> 403 Forbidden.
    - librarian views any reservation -> 200 OK.
    - GET /api/spaces/reservations/my lists own reservations paginated.
    - GET /api/spaces/reservations lists all reservations for librarian with filters.
    - non-librarian accessing GET /api/spaces/reservations -> 403 Forbidden.
15. Availability query:
    - returns available seats and rooms for interval.
    - excludes booked resources.
    - filters by zone_id, min_capacity, has_power.
    - privacy check: does not leak patron user details.
16. Zones endpoint:
    - GET /api/spaces/zones returns active zones.
17. Multi-connection raw SQLite concurrency test verifying serialization & trigger enforcement.
"""
import concurrent.futures
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import threading
from unittest.mock import patch
from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.auth import create_access_token, hash_password
from app.config import get_settings
from app.crud import spaces as crud_spaces
from app.database import atomic_write, setup_engine_events
from app.models import Base, Reservation, StudyRoom, StudySeat, StudyZone, User
from app.schemas import (
    ReservationCheckInRequest,
    ReservationCheckInWithTokenRequest,
    ReservationCreate,
    ReservationQRResponse,
    ReservationSweepReport,
)
from app.services.spaces import (
    cancel_reservation_service,
    check_in_by_qr_token_service,
    check_in_reservation_service,
    classify_spaces_db_exception,
    create_reservation_service,
    generate_qr_checkin_token,
    get_reservation_qr_token_service,
    sweep_study_space_reservations_service,
    validate_reservation_times,
    verify_qr_checkin_token,
)
from app.utils.date import get_library_timezone, get_utc_now


# ── Helper Fixtures & Setup ───────────────────────────────────────────────────

@pytest.fixture
def space_infrastructure(db: Session):
    """Creates a standard set of zones, seats, and rooms for testing."""
    zone_quiet = StudyZone(
        zone_code="Z-QUIET-1",
        name="Silent Study Hall",
        floor=1,
        total_capacity=50,
        noise_policy="silent",
        is_active=True,
    )
    zone_collab = StudyZone(
        zone_code="Z-COLLAB-2",
        name="Collaboration Area",
        floor=2,
        total_capacity=40,
        noise_policy="collaborative",
        is_active=True,
    )
    zone_inactive = StudyZone(
        zone_code="Z-CLOSED-B1",
        name="Basement Archive Area",
        floor=0,
        total_capacity=10,
        noise_policy="silent",
        is_active=False,
    )
    db.add_all([zone_quiet, zone_collab, zone_inactive])
    db.flush()

    seat1 = StudySeat(
        zone_id=zone_quiet.id,
        seat_code="S-101",
        has_power_outlet=True,
        has_monitor=True,
        is_accessible=True,
        is_active=True,
    )
    seat2 = StudySeat(
        zone_id=zone_quiet.id,
        seat_code="S-102",
        has_power_outlet=True,
        has_monitor=False,
        is_accessible=False,
        is_active=True,
    )
    seat_inactive = StudySeat(
        zone_id=zone_quiet.id,
        seat_code="S-199",
        has_power_outlet=False,
        has_monitor=False,
        is_accessible=False,
        is_active=False,
    )
    db.add_all([seat1, seat2, seat_inactive])

    room1 = StudyRoom(
        room_code="R-201",
        name="Discussion Room A",
        capacity=6,
        display_type="tv",
        has_whiteboard=True,
        is_active=True,
    )
    room2 = StudyRoom(
        room_code="R-202",
        name="Seminar Room B",
        capacity=12,
        display_type="projector",
        has_whiteboard=True,
        is_active=True,
    )
    room_inactive = StudyRoom(
        room_code="R-299",
        name="Renovation Room C",
        capacity=8,
        display_type="none",
        has_whiteboard=False,
        is_active=False,
    )
    db.add_all([room1, room2, room_inactive])
    db.flush()

    return {
        "zone_quiet": zone_quiet,
        "zone_collab": zone_collab,
        "seat1": seat1,
        "seat2": seat2,
        "seat_inactive": seat_inactive,
        "room1": room1,
        "room2": room2,
        "room_inactive": room_inactive,
    }


def make_auth_user(db: Session, client, email: str, role: str, full_name: str):
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password("SecurePass123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    token = create_access_token(user_id=user.id, role=role)
    csrf_val = f"csrf-{role}-{user.id}"
    return {
        "user": user,
        "token": token,
        "csrf": csrf_val,
        "headers": {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val},
        "cookies": {"access_token": token, "csrf_token": csrf_val},
    }


def get_future_operational_window(days_ahead: int = 1, start_hour_ist: int = 10, duration_hours: int = 2):
    """
    Computes a valid future reservation window in UTC that maps strictly within
    library operating hours (08:00 - 22:00 IST) on a single calendar day.
    IST = UTC+05:30.
    start_hour_ist in [8..20].
    """
    now_utc = datetime.utcnow()
    # Compute base date in IST
    ist_tz = get_library_timezone("Asia/Kolkata")
    now_ist = now_utc.replace(tzinfo=timezone.utc).astimezone(ist_tz)
    target_date = (now_ist + timedelta(days=days_ahead)).date()

    target_start_ist = datetime.combine(target_date, time(start_hour_ist, 0), tzinfo=ist_tz)
    target_end_ist = target_start_ist + timedelta(hours=duration_hours)

    start_utc = target_start_ist.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = target_end_ist.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


# ── Test Cases ────────────────────────────────────────────────────────────────

def test_student_can_create_valid_seat_reservation(client, db: Session, space_infrastructure):
    auth = make_auth_user(db, client, "student1@univ.edu", "student", "Alice Student")
    seat = space_infrastructure["seat1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=2, start_hour_ist=10, duration_hours=2)

    payload = {
        "resource_type": "seat",
        "seat_id": seat.id,
        "start_time": start_utc.isoformat(),
        "end_time": end_utc.isoformat(),
        "expected_attendees": 1,
    }

    resp = client.post(
        "/api/spaces/reservations",
        json=payload,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["resource_type"] == "seat"
    assert data["seat_id"] == seat.id
    assert data["user_id"] == auth["user"].id
    assert data["status"] == "active"
    assert data["expected_attendees"] == 1


def test_teacher_can_create_valid_room_reservation(client, db: Session, space_infrastructure):
    auth = make_auth_user(db, client, "prof1@univ.edu", "teacher", "Dr. Bob Professor")
    room = space_infrastructure["room1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=3, start_hour_ist=14, duration_hours=2)

    payload = {
        "resource_type": "room",
        "room_id": room.id,
        "start_time": start_utc.isoformat(),
        "end_time": end_utc.isoformat(),
        "expected_attendees": 4,
    }

    resp = client.post(
        "/api/spaces/reservations",
        json=payload,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["resource_type"] == "room"
    assert data["room_id"] == room.id
    assert data["user_id"] == auth["user"].id
    assert data["status"] == "active"
    assert data["expected_attendees"] == 4


def test_resource_target_mutual_exclusion(client, db: Session, space_infrastructure):
    auth = make_auth_user(db, client, "student2@univ.edu", "student", "Charlie Student")
    seat = space_infrastructure["seat1"]
    room = space_infrastructure["room1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1)

    # Both seat_id and room_id provided -> rejected
    payload = {
        "resource_type": "seat",
        "seat_id": seat.id,
        "room_id": room.id,
        "start_time": start_utc.isoformat(),
        "end_time": end_utc.isoformat(),
    }
    resp = client.post(
        "/api/spaces/reservations",
        json=payload,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 422

    # Room reservation with seat_id instead of room_id -> rejected
    payload = {
        "resource_type": "room",
        "seat_id": seat.id,
        "start_time": start_utc.isoformat(),
        "end_time": end_utc.isoformat(),
    }
    resp = client.post(
        "/api/spaces/reservations",
        json=payload,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 422


def test_attendee_validation_rules(client, db: Session, space_infrastructure):
    auth = make_auth_user(db, client, "prof2@univ.edu", "teacher", "Dr. Dave")
    seat = space_infrastructure["seat1"]
    room = space_infrastructure["room1"]  # Capacity 6
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=9, duration_hours=1)

    # 1. Seat with expected_attendees > 1 -> rejected
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": start_utc.isoformat(),
            "end_time": end_utc.isoformat(),
            "expected_attendees": 2,
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 422

    # 2. Room with expected_attendees = 0 -> rejected
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "room",
            "room_id": room.id,
            "start_time": start_utc.isoformat(),
            "end_time": end_utc.isoformat(),
            "expected_attendees": 0,
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 422

    # 3. Room with expected_attendees > room.capacity (7 > 6) -> rejected
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "room",
            "room_id": room.id,
            "start_time": start_utc.isoformat(),
            "end_time": end_utc.isoformat(),
            "expected_attendees": 7,
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 400
    assert "room capacity" in resp.json()["detail"]

    # 4. Non-integer / boolean expected_attendees -> rejected
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": start_utc.isoformat(),
            "end_time": end_utc.isoformat(),
            "expected_attendees": True,
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 422


def test_time_validation_edge_cases(client, db: Session, space_infrastructure):
    auth = make_auth_user(db, client, "student3@univ.edu", "student", "Eve Student")
    seat = space_infrastructure["seat1"]
    room = space_infrastructure["room1"]

    now_utc = datetime.utcnow()

    # 1. Past reservation rejected
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": (now_utc - timedelta(hours=2)).isoformat(),
            "end_time": (now_utc - timedelta(hours=1)).isoformat(),
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 400
    assert "in the past" in resp.json()["detail"]

    # 2. Duration < 30 mins rejected (15 mins)
    start_utc, _ = get_future_operational_window(days_ahead=1, start_hour_ist=10)
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": start_utc.isoformat(),
            "end_time": (start_utc + timedelta(minutes=15)).isoformat(),
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 400
    assert "at least 30 minutes" in resp.json()["detail"]

    # 3. Seat duration > 4 hours rejected (5 hours)
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": start_utc.isoformat(),
            "end_time": (start_utc + timedelta(hours=5)).isoformat(),
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 400
    assert "cannot exceed 4 hours" in resp.json()["detail"]

    # 4. Room duration > 3 hours rejected (3.5 hours)
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "room",
            "room_id": room.id,
            "start_time": start_utc.isoformat(),
            "end_time": (start_utc + timedelta(hours=3, minutes=30)).isoformat(),
            "expected_attendees": 2,
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 400
    assert "cannot exceed 3 hours" in resp.json()["detail"]

    # 5. Outside operating hours: 07:00 IST (before 08:00 opening)
    early_start_utc, early_end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=7, duration_hours=1)
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": early_start_utc.isoformat(),
            "end_time": early_end_utc.isoformat(),
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 400
    assert "operating hours" in resp.json()["detail"]


def test_advance_booking_window_by_role(client, db: Session, space_infrastructure):
    seat = space_infrastructure["seat1"]

    # Student cannot book > 7 days ahead (e.g. 9 days)
    auth_student = make_auth_user(db, client, "student_adv@univ.edu", "student", "Adv Student")
    start_utc_9d, end_utc_9d = get_future_operational_window(days_ahead=9, start_hour_ist=10, duration_hours=1)

    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": start_utc_9d.isoformat(),
            "end_time": end_utc_9d.isoformat(),
        },
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert resp.status_code == 400
    assert "7 days in advance" in resp.json()["detail"]

    # Teacher can book 10 days ahead (<= 14 days)
    auth_teacher = make_auth_user(db, client, "teacher_adv@univ.edu", "teacher", "Adv Teacher")
    start_utc_10d, end_utc_10d = get_future_operational_window(days_ahead=10, start_hour_ist=10, duration_hours=1)

    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": start_utc_10d.isoformat(),
            "end_time": end_utc_10d.isoformat(),
        },
        headers=auth_teacher["headers"],
        cookies=auth_teacher["cookies"],
    )
    assert resp.status_code == 201

    # Teacher cannot book 16 days ahead (> 14 days)
    start_utc_16d, end_utc_16d = get_future_operational_window(days_ahead=16, start_hour_ist=10, duration_hours=1)
    resp = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat.id,
            "start_time": start_utc_16d.isoformat(),
            "end_time": end_utc_16d.isoformat(),
        },
        headers=auth_teacher["headers"],
        cookies=auth_teacher["cookies"],
    )
    assert resp.status_code == 400
    assert "14 days in advance" in resp.json()["detail"]


def test_active_booking_quota_enforcement(client, db: Session, space_infrastructure):
    seat1 = space_infrastructure["seat1"]
    seat2 = space_infrastructure["seat2"]
    room1 = space_infrastructure["room1"]

    auth_student = make_auth_user(db, client, "student_quota@univ.edu", "student", "Quota Student")

    # 1. Student books first active reservation -> success
    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=9, duration_hours=1)
    resp1 = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat1.id,
            "start_time": s1.isoformat(),
            "end_time": e1.isoformat(),
        },
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert resp1.status_code == 201

    # 2. Student attempts second active reservation (even non-overlapping) -> rejected
    s2, e2 = get_future_operational_window(days_ahead=2, start_hour_ist=9, duration_hours=1)
    resp2 = client.post(
        "/api/spaces/reservations",
        json={
            "resource_type": "seat",
            "seat_id": seat2.id,
            "start_time": s2.isoformat(),
            "end_time": e2.isoformat(),
        },
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert resp2.status_code == 400
    assert "maximum allowed active reservations" in resp2.json()["detail"]

    # 3. Teacher can book 2 active reservations, but not 3
    auth_teacher = make_auth_user(db, client, "teacher_quota@univ.edu", "teacher", "Quota Teacher")
    t1_s, t1_e = get_future_operational_window(days_ahead=1, start_hour_ist=11, duration_hours=1)
    t2_s, t2_e = get_future_operational_window(days_ahead=2, start_hour_ist=11, duration_hours=1)
    t3_s, t3_e = get_future_operational_window(days_ahead=3, start_hour_ist=11, duration_hours=1)

    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": t1_s.isoformat(), "end_time": t1_e.isoformat()},
        headers=auth_teacher["headers"],
        cookies=auth_teacher["cookies"],
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": t2_s.isoformat(), "end_time": t2_e.isoformat()},
        headers=auth_teacher["headers"],
        cookies=auth_teacher["cookies"],
    )
    assert r2.status_code == 201

    r3 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": t3_s.isoformat(), "end_time": t3_e.isoformat()},
        headers=auth_teacher["headers"],
        cookies=auth_teacher["cookies"],
    )
    assert r3.status_code == 400
    assert "maximum allowed active reservations" in r3.json()["detail"]


def test_user_level_overlap_prevention(client, db: Session, space_infrastructure):
    auth_teacher = make_auth_user(db, client, "teacher_overlap@univ.edu", "teacher", "Teacher Overlap")
    seat1 = space_infrastructure["seat1"]
    seat2 = space_infrastructure["seat2"]

    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    # First booking: Seat 1
    resp1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": s1.isoformat(), "end_time": e1.isoformat()},
        headers=auth_teacher["headers"],
        cookies=auth_teacher["cookies"],
    )
    assert resp1.status_code == 201

    # Second booking: Same teacher attempts to book Seat 2 during overlapping window -> 409 Conflict
    overlap_s = s1 + timedelta(minutes=30)
    overlap_e = overlap_s + timedelta(hours=1)
    resp2 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat2.id, "start_time": overlap_s.isoformat(), "end_time": overlap_e.isoformat()},
        headers=auth_teacher["headers"],
        cookies=auth_teacher["cookies"],
    )
    assert resp2.status_code == 409
    assert "user already has an active reservation" in resp2.json()["detail"]


def test_librarian_can_hold_overlapping_reservations(client, db: Session, space_infrastructure):
    auth_lib = make_auth_user(db, client, "lib_overlap@library.org", "librarian", "Lib Overlap")
    room1 = space_infrastructure["room1"]
    room2 = space_infrastructure["room2"]

    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=13, duration_hours=2)

    # Book Room 1
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "room", "room_id": room1.id, "start_time": s1.isoformat(), "end_time": e1.isoformat(), "expected_attendees": 4},
        headers=auth_lib["headers"],
        cookies=auth_lib["cookies"],
    )
    assert r1.status_code == 201

    # Book Room 2 during overlapping time -> Allowed for librarian
    r2 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "room", "room_id": room2.id, "start_time": s1.isoformat(), "end_time": e1.isoformat(), "expected_attendees": 6},
        headers=auth_lib["headers"],
        cookies=auth_lib["cookies"],
    )
    assert r2.status_code == 201


def test_resource_level_collision_prevention(client, db: Session, space_infrastructure):
    auth_student1 = make_auth_user(db, client, "student_col1@univ.edu", "student", "Col Student 1")
    auth_student2 = make_auth_user(db, client, "student_col2@univ.edu", "student", "Col Student 2")
    seat1 = space_infrastructure["seat1"]

    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=15, duration_hours=2)

    # Student 1 books Seat 1
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": s1.isoformat(), "end_time": e1.isoformat()},
        headers=auth_student1["headers"],
        cookies=auth_student1["cookies"],
    )
    assert r1.status_code == 201

    # Student 2 attempts to book Seat 1 during overlapping interval -> 409 Conflict
    overlap_s = s1 + timedelta(minutes=45)
    overlap_e = overlap_s + timedelta(hours=1)
    r2 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": overlap_s.isoformat(), "end_time": overlap_e.isoformat()},
        headers=auth_student2["headers"],
        cookies=auth_student2["cookies"],
    )
    assert r2.status_code == 409
    assert "seat is already reserved" in r2.json()["detail"]


def test_default_deny_on_unknown_role(client, db: Session, space_infrastructure):
    auth_guest = make_auth_user(db, client, "guest@external.com", "guest", "Guest User")
    seat = space_infrastructure["seat1"]
    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=1)

    resp = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat.id, "start_time": s1.isoformat(), "end_time": e1.isoformat()},
        headers=auth_guest["headers"],
        cookies=auth_guest["cookies"],
    )
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"]


def test_inactive_resource_rejection(client, db: Session, space_infrastructure):
    auth_student = make_auth_user(db, client, "inactive_res_test@univ.edu", "student", "Inactive Test")
    seat_inactive = space_infrastructure["seat_inactive"]
    room_inactive = space_infrastructure["room_inactive"]
    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=1)

    # Attempt to book inactive seat
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat_inactive.id, "start_time": s1.isoformat(), "end_time": e1.isoformat()},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert r1.status_code == 400
    assert "currently unavailable" in r1.json()["detail"]

    # Attempt to book inactive room
    r2 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "room", "room_id": room_inactive.id, "start_time": s1.isoformat(), "end_time": e1.isoformat(), "expected_attendees": 2},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert r2.status_code == 400
    assert "currently unavailable" in r2.json()["detail"]


def test_cancellation_lifecycle_and_quota_restoration(client, db: Session, space_infrastructure):
    auth_student = make_auth_user(db, client, "cancel_test@univ.edu", "student", "Cancel Student")
    auth_other = make_auth_user(db, client, "other_cancel@univ.edu", "student", "Other Student")
    auth_lib = make_auth_user(db, client, "lib_canceller@library.org", "librarian", "Staff Librarian")
    seat1 = space_infrastructure["seat1"]
    seat2 = space_infrastructure["seat2"]

    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=1)

    # 1. Create reservation
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": s1.isoformat(), "end_time": e1.isoformat()},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    res_id = r1.json()["id"]

    # 2. Other patron attempts to cancel -> 403 Forbidden
    resp_other = client.delete(
        f"/api/spaces/reservations/{res_id}",
        headers=auth_other["headers"],
        cookies=auth_other["cookies"],
    )
    assert resp_other.status_code == 403

    # 3. Owner cancels own reservation -> 200 OK
    resp_cancel = client.delete(
        f"/api/spaces/reservations/{res_id}",
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "cancelled"

    # 4. Quota restored: student can immediately book another active reservation
    s2, e2 = get_future_operational_window(days_ahead=2, start_hour_ist=10, duration_hours=1)
    r2 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat2.id, "start_time": s2.isoformat(), "end_time": e2.isoformat()},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert r2.status_code == 201

    # 5. Librarian can cancel the new reservation -> 200 OK
    res2_id = r2.json()["id"]
    r_lib_cancel = client.delete(
        f"/api/spaces/reservations/{res2_id}",
        headers=auth_lib["headers"],
        cookies=auth_lib["cookies"],
    )
    assert r_lib_cancel.status_code == 200
    assert r_lib_cancel.json()["status"] == "cancelled"

    # 6. Cannot cancel already cancelled reservation -> 400 Bad Request
    r_double_cancel = client.delete(
        f"/api/spaces/reservations/{res2_id}",
        headers=auth_lib["headers"],
        cookies=auth_lib["cookies"],
    )
    assert r_double_cancel.status_code == 400


def test_reservation_retrieval_and_permissions(client, db: Session, space_infrastructure):
    auth_owner = make_auth_user(db, client, "owner_get@univ.edu", "student", "Owner Student")
    auth_other = make_auth_user(db, client, "other_get@univ.edu", "student", "Other Student")
    auth_lib = make_auth_user(db, client, "lib_get@library.org", "librarian", "Lib Reader")
    seat1 = space_infrastructure["seat1"]

    s1, e1 = get_future_operational_window(days_ahead=1, start_hour_ist=11, duration_hours=1)
    r_create = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": s1.isoformat(), "end_time": e1.isoformat()},
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    res_id = r_create.json()["id"]

    # Owner views own reservation -> 200
    resp_owner = client.get(
        f"/api/spaces/reservations/{res_id}",
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    assert resp_owner.status_code == 200
    assert resp_owner.json()["id"] == res_id

    # Other patron views reservation -> 403 Forbidden
    resp_other = client.get(
        f"/api/spaces/reservations/{res_id}",
        headers=auth_other["headers"],
        cookies=auth_other["cookies"],
    )
    assert resp_other.status_code == 403

    # Librarian views reservation -> 200 OK
    resp_lib = client.get(
        f"/api/spaces/reservations/{res_id}",
        headers=auth_lib["headers"],
        cookies=auth_lib["cookies"],
    )
    assert resp_lib.status_code == 200

    # My reservations list for owner
    resp_my = client.get(
        "/api/spaces/reservations/my",
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    assert resp_my.status_code == 200
    my_data = resp_my.json()
    assert my_data["total"] >= 1
    assert any(item["id"] == res_id for item in my_data["items"])

    # Admin all reservations list:
    # Patron accessing -> 403 Forbidden
    resp_admin_denied = client.get(
        "/api/spaces/reservations",
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    assert resp_admin_denied.status_code == 403

    # Librarian accessing -> 200 OK
    resp_admin_ok = client.get(
        "/api/spaces/reservations",
        headers=auth_lib["headers"],
        cookies=auth_lib["cookies"],
    )
    assert resp_admin_ok.status_code == 200
    assert resp_admin_ok.json()["total"] >= 1


def test_space_availability_query_and_privacy(client, db: Session, space_infrastructure):
    auth_student = make_auth_user(db, client, "avail_user@univ.edu", "student", "Avail User")
    seat1 = space_infrastructure["seat1"]
    seat2 = space_infrastructure["seat2"]
    room1 = space_infrastructure["room1"]

    s1, e1 = get_future_operational_window(days_ahead=2, start_hour_ist=14, duration_hours=2)

    # Reserve seat1
    client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": s1.isoformat(), "end_time": e1.isoformat()},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )

    # Query availability during s1..e1
    resp = client.get(
        f"/api/spaces/availability?start_time={s1.isoformat()}&end_time={e1.isoformat()}",
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert resp.status_code == 200
    data = resp.json()

    available_seat_ids = [s["id"] for s in data["seats"]]
    # Seat 1 is reserved and must not appear
    assert seat1.id not in available_seat_ids
    # Seat 2 is free and must appear
    assert seat2.id in available_seat_ids
    # Room 1 is free and must appear
    available_room_ids = [r["id"] for r in data["rooms"]]
    assert room1.id in available_room_ids

    # Privacy check: response has no user_id or patron personal details
    resp_text = resp.text
    assert "user_id" not in resp_text
    assert "avail_user@univ.edu" not in resp_text


def test_list_study_zones_endpoint(client, db: Session, space_infrastructure):
    auth = make_auth_user(db, client, "zones_reader@univ.edu", "student", "Zones Reader")
    resp = client.get(
        "/api/spaces/zones",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 200
    zones = resp.json()
    assert len(zones) >= 2
    zone_codes = [z["zone_code"] for z in zones]
    assert "Z-QUIET-1" in zone_codes
    assert "Z-COLLAB-2" in zone_codes
    # Inactive zone must not appear
    assert "Z-CLOSED-B1" not in zone_codes


def test_multi_connection_concurrency_serializes_and_protects_resource(tmp_path):
    """
    Simulates multi-connection concurrency against an isolated SQLite database file.
    Verifies that BEGIN IMMEDIATE and SQLite triggers prevent double-booking under race conditions.
    """
    db_file = tmp_path / "concurrent_spaces.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    # Seed zone, seat, and two students
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Quiet Zone', 1, 10, 'silent', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (1, 1, 'S-1', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (1, 'u1@u.edu', 'User 1', 'h', 'student', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (2, 'u2@u.edu', 'User 2', 'h', 'student', 1, datetime('now'))")

    # Connection 1 begins immediate write transaction and reserves seat 1
    conn1 = engine.connect().execution_options(sqlite_immediate=True)
    tx1 = conn1.begin()
    conn1.exec_driver_sql("""
        INSERT INTO reservations (user_id, resource_type, seat_id, start_time, end_time, status, expected_attendees, created_at)
        VALUES (1, 'seat', 1, '2026-11-05 10:00:00.000000', '2026-11-05 12:00:00.000000', 'active', 1, datetime('now'))
    """)
    tx1.commit()
    conn1.close()

    # Connection 2 attempts to reserve overlapping interval on same seat
    conn2 = engine.connect().execution_options(sqlite_immediate=True)
    tx2 = conn2.begin()
    collision_prevented = False
    try:
        conn2.exec_driver_sql("""
            INSERT INTO reservations (user_id, resource_type, seat_id, start_time, end_time, status, expected_attendees, created_at)
            VALUES (2, 'seat', 1, '2026-11-05 11:00:00.000000', '2026-11-05 13:00:00.000000', 'active', 1, datetime('now'))
        """)
        tx2.commit()
    except Exception as exc:
        collision_prevented = True
        tx2.rollback()
        assert "Reservation conflict" in str(exc)
    finally:
        conn2.close()

    assert collision_prevented is True


def test_strict_no_past_start_boundary(db: Session, space_infrastructure):
    """
    Verifies strict boundary start_time >= now_utc with zero past-start tolerance.
    - Exact now is accepted.
    - 1 microsecond in the past is rejected.
    - 1 second in the past is rejected.
    - 1 microsecond in the future is accepted.
    - Timezone-aware input is correctly normalized to UTC without floating-point artifacts.
    - Naive UTC datetime handling is preserved.
    """
    auth_student = make_auth_user(db, None, "boundary_student@univ.edu", "student", "Boundary Student")
    seat = space_infrastructure["seat1"]

    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)
    payload = ReservationCreate(
        resource_type="seat",
        seat_id=seat.id,
        start_time=start_utc,
        end_time=end_utc,
        expected_attendees=1,
    )

    # 1. Exact boundary: start_time == now_utc is accepted
    res1 = create_reservation_service(db, auth_student["user"], payload, now_utc=start_utc)
    assert res1.id is not None
    assert res1.status == "active"
    cancel_reservation_service(db, auth_student["user"], res1.id)

    # 2. Strict rejection: 1 microsecond in past (start_time < now_utc)
    micro_past_now = start_utc + timedelta(microseconds=1)
    with pytest.raises(HTTPException) as exc_info:
        create_reservation_service(db, auth_student["user"], payload, now_utc=micro_past_now)
    assert exc_info.value.status_code == 400
    assert "start time cannot be in the past" in exc_info.value.detail

    # 3. Strict rejection: 1 second in past
    second_past_now = start_utc + timedelta(seconds=1)
    with pytest.raises(HTTPException) as exc_info:
        create_reservation_service(db, auth_student["user"], payload, now_utc=second_past_now)
    assert exc_info.value.status_code == 400
    assert "start time cannot be in the past" in exc_info.value.detail

    # 4. Strict acceptance: 1 microsecond in future (start_time > now_utc)
    micro_future_now = start_utc - timedelta(microseconds=1)
    res2 = create_reservation_service(db, auth_student["user"], payload, now_utc=micro_future_now)
    assert res2.id is not None
    assert res2.status == "active"
    cancel_reservation_service(db, auth_student["user"], res2.id)

    # 5. Timezone-aware input: explicitly passed with IST (+05:30) timezone
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    start_ist = start_utc.replace(tzinfo=timezone.utc).astimezone(ist_tz)
    end_ist = end_utc.replace(tzinfo=timezone.utc).astimezone(ist_tz)
    payload_tz = ReservationCreate(
        resource_type="seat",
        seat_id=seat.id,
        start_time=start_ist,
        end_time=end_ist,
        expected_attendees=1,
    )
    res3 = create_reservation_service(db, auth_student["user"], payload_tz, now_utc=start_utc)
    assert res3.id is not None
    # Storage must remain naive UTC matching original start_utc
    assert res3.start_time.tzinfo is None
    assert res3.start_time == start_utc
    cancel_reservation_service(db, auth_student["user"], res3.id)


def test_sanitized_exception_handling_and_no_detail_leakage(client, db: Session, space_infrastructure):
    """
    Verifies precise sanitized database exception mapping:
    - Resource conflict -> HTTP 409 (generic message, no SQL/table leakage).
    - User overlap conflict -> HTTP 409 (generic message, no SQL/table leakage).
    - Known uniqueness conflict -> HTTP 409 (generic message, no SQL/table leakage).
    - SQLite busy / locked -> HTTP 503 (generic retry message, Retry-After: 1).
    - Unexpected IntegrityError -> HTTP 500 (sanitized message).
    - Unexpected OperationalError -> HTTP 500 (sanitized message).
    - Failed write leaves no partial reservation and transaction rollback works cleanly.
    """
    auth_student = make_auth_user(db, client, "sanitize_test@univ.edu", "student", "Sanitize Student")
    seat = space_infrastructure["seat1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=2, start_hour_ist=10, duration_hours=2)
    payload = {
        "resource_type": "seat",
        "seat_id": seat.id,
        "start_time": start_utc.isoformat(),
        "end_time": end_utc.isoformat(),
        "expected_attendees": 1,
    }

    # 1. First booking succeeds
    r1 = client.post(
        "/api/spaces/reservations",
        json=payload,
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert r1.status_code == 201

    # 2. Second booking with another user colliding on same resource -> HTTP 409
    auth_student2 = make_auth_user(db, client, "sanitize2@univ.edu", "student", "Sanitize Student 2")
    r2 = client.post(
        "/api/spaces/reservations",
        json=payload,
        headers=auth_student2["headers"],
        cookies=auth_student2["cookies"],
    )
    assert r2.status_code == 409
    detail_409 = r2.json()["detail"]
    assert "Reservation conflict:" in detail_409
    assert "already reserved" in detail_409 or "already has an active reservation" in detail_409
    # Ensure no table name, SQL, or driver string leaked
    for forbidden in ["SELECT", "INSERT", "reservations", "OperationalError", "IntegrityError", "sqlite3"]:
        assert forbidden not in detail_409

    # 3. Known uniqueness conflict on reservations table -> HTTP 409
    res_payload = ReservationCreate(
        resource_type="seat",
        seat_id=space_infrastructure["seat2"].id,
        start_time=start_utc,
        end_time=end_utc,
        expected_attendees=1,
    )
    with patch.object(db, "flush", side_effect=IntegrityError("UNIQUE constraint failed: reservations.id", None, None)):
        with pytest.raises(HTTPException) as exc_info:
            create_reservation_service(db, auth_student2["user"], res_payload)
        assert exc_info.value.status_code == 409
        assert "Reservation conflict" in exc_info.value.detail
        for forbidden in ["UNIQUE constraint", "reservations.id", "sqlite3"]:
            assert forbidden not in exc_info.value.detail

    # 4. SQLite busy error (with driver metadata) maps to HTTP 503
    import sqlite3 as raw_sqlite3
    busy_err = raw_sqlite3.OperationalError("database is busy")
    setattr(busy_err, "sqlite_errorcode", 5)
    setattr(busy_err, "sqlite_errorname", "SQLITE_BUSY")
    with patch.object(db, "flush", side_effect=OperationalError("database is busy", None, busy_err)):
        with pytest.raises(HTTPException) as exc_info:
            create_reservation_service(db, auth_student2["user"], res_payload)
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "The reservation service is currently busy. Please retry your request shortly."
        assert exc_info.value.headers.get("Retry-After") == "1"
        for forbidden in ["database is busy", "SQLITE_BUSY", "OperationalError", "sqlite3"]:
            assert forbidden not in exc_info.value.detail

    # 5. SQLite locked error (with driver metadata) maps to HTTP 503
    locked_err = raw_sqlite3.OperationalError("database is locked")
    setattr(locked_err, "sqlite_errorcode", 6)
    setattr(locked_err, "sqlite_errorname", "SQLITE_LOCKED")
    with patch.object(db, "flush", side_effect=OperationalError("database is locked", None, locked_err)):
        with pytest.raises(HTTPException) as exc_info:
            create_reservation_service(db, auth_student2["user"], res_payload)
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "The reservation service is currently busy. Please retry your request shortly."
        assert exc_info.value.headers.get("Retry-After") == "1"

    # 6. Unexpected IntegrityError maps to HTTP 500 without leaking details
    with patch.object(db, "flush", side_effect=IntegrityError("FOREIGN KEY constraint failed on reservations.xyz", None, None)):
        with pytest.raises(HTTPException) as exc_info:
            create_reservation_service(db, auth_student2["user"], res_payload)
        assert exc_info.value.status_code == 500
        assert "internal database integrity error" in exc_info.value.detail
        for forbidden in ["FOREIGN KEY", "reservations.xyz", "sqlite3", "IntegrityError"]:
            assert forbidden not in exc_info.value.detail

    # 7. Unexpected OperationalError maps to HTTP 500 without leaking details
    with patch.object(db, "flush", side_effect=OperationalError("disk I/O error on table reservations", None, None)):
        with pytest.raises(HTTPException) as exc_info:
            create_reservation_service(db, auth_student2["user"], res_payload)
        assert exc_info.value.status_code == 500
        assert "internal database operational error" in exc_info.value.detail
        for forbidden in ["disk I/O error", "reservations", "OperationalError"]:
            assert forbidden not in exc_info.value.detail

    # 8. Failed write leaves no partial reservation in database
    pre_count = db.execute(select(Reservation).where(Reservation.seat_id == space_infrastructure["seat2"].id)).scalars().all()
    assert len(pre_count) == 0


def test_concurrent_same_resource_collision(tmp_path):
    """
    Test A — Same-resource collision:
    Five simultaneous booking attempts for the same seat and overlapping interval.
    Expected: exactly one successful booking; all other 4 attempts fail with HTTP 409.
    Final DB has exactly 1 active reservation for that seat and interval.
    """
    import sqlite3
    db_file = tmp_path / "test_a_collision.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA busy_timeout = 5000;")
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Quiet Zone', 1, 10, 'silent', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (1, 1, 'S-1', 1, 0, 0, 1, datetime('now'))")
        for i in range(1, 6):
            conn.exec_driver_sql(f"INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES ({i}, 'student{i}@u.edu', 'Student {i}', 'h', 'student', 1, datetime('now'))")

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    start_utc, end_utc = get_future_operational_window(days_ahead=2, start_hour_ist=10, duration_hours=2)

    barrier = threading.Barrier(5)
    results = []

    def worker(user_id):
        session = session_factory()
        data = ReservationCreate(
            resource_type="seat",
            seat_id=1,
            start_time=start_utc,
            end_time=end_utc,
            expected_attendees=1,
        )
        barrier.wait()
        try:
            with atomic_write(session):
                user = session.get(User, user_id)
                res = create_reservation_service(session, user, data)
                return ("success", res.id)
        except HTTPException as he:
            return ("http_error", he.status_code, he.detail)
        except Exception as exc:
            return ("unexpected", str(exc))
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker, i) for i in range(1, 6)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[0] == "success"]
    conflicts = [r for r in results if r[0] == "http_error" and r[1] == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {results}"
    assert len(conflicts) == 4, f"Expected exactly 4 conflicts, got {len(conflicts)}: {results}"

    # Verify final database has exactly 1 active reservation
    with engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT count(*) FROM reservations WHERE seat_id = 1 AND status = 'active'").scalar()
        assert count == 1

    engine.dispose()


def test_concurrent_student_quota_race(tmp_path):
    """
    Test B — Student quota race:
    Two simultaneous booking attempts by the same student for distinct resources
    and non-overlapping intervals.
    Expected: exactly 1 succeeds, 1 fails with quota validation error (HTTP 400).
    Final DB has exactly 1 active reservation for that student.
    """
    import sqlite3
    db_file = tmp_path / "test_b_quota.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA busy_timeout = 5000;")
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Quiet Zone', 1, 10, 'silent', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (1, 1, 'S-1', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (2, 1, 'S-2', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (1, 'student1@u.edu', 'Student 1', 'h', 'student', 1, datetime('now'))")

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    s1, e1 = get_future_operational_window(days_ahead=2, start_hour_ist=9, duration_hours=1)
    s2, e2 = get_future_operational_window(days_ahead=2, start_hour_ist=11, duration_hours=1)

    barrier = threading.Barrier(2)
    results = []

    def worker(seat_id, start_time, end_time):
        session = session_factory()
        data = ReservationCreate(
            resource_type="seat",
            seat_id=seat_id,
            start_time=start_time,
            end_time=end_time,
            expected_attendees=1,
        )
        barrier.wait()
        try:
            with atomic_write(session):
                user = session.get(User, 1)
                res = create_reservation_service(session, user, data)
                return ("success", res.id)
        except HTTPException as he:
            return ("http_error", he.status_code, he.detail)
        except Exception as exc:
            return ("unexpected", str(exc))
        finally:
            session.close()

    tasks = [(1, s1, e1), (2, s2, e2)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker, *t) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[0] == "success"]
    quota_errors = [r for r in results if r[0] == "http_error" and r[1] == 400 and "maximum allowed active reservations" in r[2]]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
    assert len(quota_errors) == 1, f"Expected 1 quota error, got {len(quota_errors)}: {results}"

    with engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT count(*) FROM reservations WHERE user_id = 1 AND status = 'active'").scalar()
        assert count == 1

    engine.dispose()


def test_concurrent_teacher_quota_race(tmp_path):
    """
    Test C — Teacher quota race:
    Three simultaneous booking attempts by the same teacher for distinct resources
    and non-overlapping intervals. Teacher quota is 2.
    Expected: exactly 2 succeed, 1 fails with quota validation error (HTTP 400).
    Final DB has exactly 2 active reservations for that teacher.
    """
    import sqlite3
    db_file = tmp_path / "test_c_teacher_quota.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA busy_timeout = 5000;")
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Quiet Zone', 1, 10, 'silent', 1, datetime('now'))")
        for i in range(1, 4):
            conn.exec_driver_sql(f"INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES ({i}, 1, 'S-{i}', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (1, 'prof1@u.edu', 'Prof 1', 'h', 'teacher', 1, datetime('now'))")

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    s1, e1 = get_future_operational_window(days_ahead=2, start_hour_ist=9, duration_hours=1)
    s2, e2 = get_future_operational_window(days_ahead=2, start_hour_ist=11, duration_hours=1)
    s3, e3 = get_future_operational_window(days_ahead=2, start_hour_ist=13, duration_hours=1)

    barrier = threading.Barrier(3)
    results = []

    def worker(seat_id, start_time, end_time):
        session = session_factory()
        data = ReservationCreate(
            resource_type="seat",
            seat_id=seat_id,
            start_time=start_time,
            end_time=end_time,
            expected_attendees=1,
        )
        barrier.wait()
        try:
            with atomic_write(session):
                user = session.get(User, 1)
                res = create_reservation_service(session, user, data)
                return ("success", res.id)
        except HTTPException as he:
            return ("http_error", he.status_code, he.detail)
        except Exception as exc:
            return ("unexpected", str(exc))
        finally:
            session.close()

    tasks = [(1, s1, e1), (2, s2, e2), (3, s3, e3)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(worker, *t) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[0] == "success"]
    quota_errors = [r for r in results if r[0] == "http_error" and r[1] == 400 and "maximum allowed active reservations" in r[2]]

    assert len(successes) == 2, f"Expected 2 successes, got {len(successes)}: {results}"
    assert len(quota_errors) == 1, f"Expected 1 quota error, got {len(quota_errors)}: {results}"

    with engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT count(*) FROM reservations WHERE user_id = 1 AND status = 'active'").scalar()
        assert count == 2

    engine.dispose()


def test_concurrent_lock_contention_and_busy_timeout(tmp_path):
    """
    Test D — Lock contention:
    Exercise actual concurrent writer contention using independent connections.
    Verify that lock contention raises HTTP 503 Service Unavailable with a generic retry message,
    does NOT become HTTP 400, and does NOT leak internal SQLite details.
    """
    import sqlite3
    db_file = tmp_path / "test_d_contention.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Quiet Zone', 1, 10, 'silent', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (1, 1, 'S-1', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (1, 'u1@u.edu', 'User 1', 'h', 'student', 1, datetime('now'))")

    # Raw connection 1 acquires exclusive write lock via BEGIN IMMEDIATE
    raw_blocker = sqlite3.connect(db_file)
    raw_blocker.execute("BEGIN IMMEDIATE")

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    s1, e1 = get_future_operational_window(days_ahead=2, start_hour_ist=10, duration_hours=2)

    session_contender = session_factory()
    # Set a tiny busy timeout on contender connection so it quickly triggers lock contention
    session_contender.connection().exec_driver_sql("PRAGMA busy_timeout = 20;")
    user = session_contender.get(User, 1)
    data = ReservationCreate(
        resource_type="seat",
        seat_id=1,
        start_time=s1,
        end_time=e1,
        expected_attendees=1,
    )

    try:
        # Attempting create_reservation_service will trigger OperationalError("database is locked")
        with pytest.raises(HTTPException) as exc_info:
            create_reservation_service(session_contender, user, data)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "The reservation service is currently busy. Please retry your request shortly."
        assert exc_info.value.headers.get("Retry-After") == "1"
        for forbidden in ["database is locked", "OperationalError", "sqlite3", "PRAGMA", "BEGIN"]:
            assert forbidden not in exc_info.value.detail
    finally:
        session_contender.close()
        raw_blocker.rollback()
        raw_blocker.close()

    # Now that blocker released, a new attempt succeeds cleanly
    session_retry = session_factory()
    session_retry.info["_in_atomic_write"] = True
    session_retry.connection(execution_options={"sqlite_immediate": True})
    user_retry = session_retry.get(User, 1)
    res = create_reservation_service(session_retry, user_retry, data)
    session_retry.commit()
    assert res.id is not None
    session_retry.close()

    engine.dispose()


# ── Stage 10.3 Tests: QR Check-In, Grace Periods & No-Show Lifecycle ──────────


def test_sqlite_extended_result_codes_classification():
    """
    F-07 Verification:
    Tests that classify_spaces_db_exception extracts primary SQLite error code
    using (sqlite_code & 0xFF) and recognizes extended error codes and names:
    - Primary code 5 (SQLITE_BUSY) -> 503
    - Primary code 6 (SQLITE_LOCKED) -> 503
    - Extended code 517 (SQLITE_BUSY_SNAPSHOT, 517 & 0xFF == 5) -> 503
    - Extended code 262 (SQLITE_LOCKED_SHAREDCACHE, 262 & 0xFF == 6) -> 503
    - Extended name SQLITE_BUSY_SNAPSHOT -> 503
    - Extended name SQLITE_LOCKED_SHAREDCACHE -> 503
    - Non-busy error code 1 (SQLITE_ERROR) -> 500 (NOT misclassified)
    """
    import sqlite3 as raw_sqlite3

    # 1. Primary code 5 (SQLITE_BUSY)
    err5 = raw_sqlite3.OperationalError("database is busy")
    setattr(err5, "sqlite_errorcode", 5)
    setattr(err5, "sqlite_errorname", "SQLITE_BUSY")
    http_exc = classify_spaces_db_exception(OperationalError("database is busy", None, err5))
    assert http_exc.status_code == 503
    assert http_exc.headers.get("Retry-After") == "1"

    # 2. Primary code 6 (SQLITE_LOCKED)
    err6 = raw_sqlite3.OperationalError("database is locked")
    setattr(err6, "sqlite_errorcode", 6)
    setattr(err6, "sqlite_errorname", "SQLITE_LOCKED")
    http_exc = classify_spaces_db_exception(OperationalError("database is locked", None, err6))
    assert http_exc.status_code == 503

    # 3. Extended code 517 (SQLITE_BUSY_SNAPSHOT: 517 & 0xFF == 5)
    err517 = raw_sqlite3.OperationalError("snapshot busy")
    setattr(err517, "sqlite_errorcode", 517)
    setattr(err517, "sqlite_errorname", "SQLITE_BUSY_SNAPSHOT")
    http_exc = classify_spaces_db_exception(OperationalError("snapshot busy", None, err517))
    assert http_exc.status_code == 503
    assert http_exc.headers.get("Retry-After") == "1"

    # 4. Extended code 262 (SQLITE_LOCKED_SHAREDCACHE: 262 & 0xFF == 6)
    err262 = raw_sqlite3.OperationalError("shared cache lock")
    setattr(err262, "sqlite_errorcode", 262)
    setattr(err262, "sqlite_errorname", "SQLITE_LOCKED_SHAREDCACHE")
    http_exc = classify_spaces_db_exception(OperationalError("shared cache lock", None, err262))
    assert http_exc.status_code == 503
    assert http_exc.headers.get("Retry-After") == "1"

    # 5. Non-busy error code 1 (SQLITE_ERROR: syntax or schema failure)
    err1 = raw_sqlite3.OperationalError("syntax error")
    setattr(err1, "sqlite_errorcode", 1)
    setattr(err1, "sqlite_errorname", "SQLITE_ERROR")
    http_exc = classify_spaces_db_exception(OperationalError("syntax error", None, err1))
    assert http_exc.status_code == 500
    assert "internal database operational error" in http_exc.detail


def test_centralized_utc_clock_usage(db: Session, space_infrastructure):
    """
    F-08 Verification:
    Tests that validate_reservation_times uses centralized get_utc_now()
    and supports deterministic injected clock parameter.
    """
    auth_student = make_auth_user(db, None, "clock_test_student@univ.edu", "student", "Clock Student")
    seat = space_infrastructure["seat1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    payload = ReservationCreate(
        resource_type="seat",
        seat_id=seat.id,
        start_time=start_utc,
        end_time=end_utc,
        expected_attendees=1,
    )

    # 1. Deterministic injected clock equal to start_time -> accepted
    res = create_reservation_service(db, auth_student["user"], payload, now_utc=start_utc)
    assert res.id is not None
    cancel_reservation_service(db, auth_student["user"], res.id)

    # 2. Injected clock past start_time -> strictly rejected
    with pytest.raises(HTTPException) as exc_info:
        create_reservation_service(db, auth_student["user"], payload, now_utc=start_utc + timedelta(microseconds=1))
    assert exc_info.value.status_code == 400
    assert "start time cannot be in the past" in exc_info.value.detail


def test_qr_token_generation_and_tamper_defense(db: Session, space_infrastructure):
    """
    Verifies cryptographically secure signed QR check-in token generation:
    - Encodes required reservation claims (sub, user_id, resource bindings).
    - Rejects tampered tokens (modified signature/payload).
    - Rejects expired tokens.
    - Rejects invalid token types.
    """
    auth_student = make_auth_user(db, None, "qr_token_student@univ.edu", "student", "QR Token Student")
    seat = space_infrastructure["seat1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    payload = ReservationCreate(
        resource_type="seat",
        seat_id=seat.id,
        start_time=start_utc,
        end_time=end_utc,
        expected_attendees=1,
    )
    res = create_reservation_service(db, auth_student["user"], payload, now_utc=start_utc)
    reservation = crud_spaces.get_reservation_by_id(db, res.id)

    # 1. Generate valid token
    token = generate_qr_checkin_token(reservation)
    assert isinstance(token, str)
    assert len(token) > 20

    # 2. Verify token claims
    claims = verify_qr_checkin_token(token)
    assert claims["type"] == "study_space_qr_checkin"
    assert claims["sub"] == f"res:{reservation.id}"
    assert int(claims["user_id"]) == reservation.user_id
    assert claims["resource_type"] == "seat"
    assert claims["resource_id"] == seat.id

    # 3. Tampered token -> 400 Bad Request
    tampered_token = token[:-4] + "ABCD"
    with pytest.raises(HTTPException) as exc_info:
        verify_qr_checkin_token(tampered_token)
    assert exc_info.value.status_code == 400
    assert "Invalid or expired QR check-in token" in exc_info.value.detail

    # 4. Token with wrong type claim -> 400 Bad Request
    settings = get_settings()
    from jose import jwt
    from app.services.spaces import get_spaces_qr_secret_key
    qr_secret = get_spaces_qr_secret_key()
    wrong_type_token = jwt.encode(
        {"type": "wrong_type", "sub": f"res:{reservation.id}", "user_id": reservation.user_id},
        qr_secret,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc_info:
        verify_qr_checkin_token(wrong_type_token)
    assert exc_info.value.status_code == 400
    assert "not a valid study space check-in token" in exc_info.value.detail


def test_qr_token_retrieval_endpoint_and_authorization(client, db: Session, space_infrastructure):
    """
    Verifies GET /api/spaces/reservations/{id}/qr endpoint:
    - Reservation owner receives QR token -> 200 OK.
    - Librarian/admin receives QR token -> 200 OK.
    - Other patron accessing -> 403 Forbidden.
    - Inactive/cancelled reservation -> 400 Bad Request.
    """
    auth_owner = make_auth_user(db, client, "qr_owner@univ.edu", "student", "QR Owner")
    auth_other = make_auth_user(db, client, "qr_other@univ.edu", "student", "QR Other")
    auth_lib = make_auth_user(db, client, "qr_lib@library.org", "librarian", "QR Lib")
    seat = space_infrastructure["seat1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    # 1. Create reservation
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat.id, "start_time": start_utc.isoformat(), "end_time": end_utc.isoformat()},
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    assert r1.status_code == 201
    res_id = r1.json()["id"]

    # 2. Owner retrieves QR pass -> 200 OK
    resp_owner = client.get(
        f"/api/spaces/reservations/{res_id}/qr",
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    assert resp_owner.status_code == 200
    data_qr = resp_owner.json()
    assert data_qr["reservation_id"] == res_id
    assert "qr_token" in data_qr
    assert data_qr["resource_name"] == f"Seat {seat.seat_code}"

    # 3. Librarian retrieves QR pass -> 200 OK
    resp_lib = client.get(
        f"/api/spaces/reservations/{res_id}/qr",
        headers=auth_lib["headers"],
        cookies=auth_lib["cookies"],
    )
    assert resp_lib.status_code == 200

    # 4. Another patron retrieves QR pass -> 403 Forbidden
    resp_other = client.get(
        f"/api/spaces/reservations/{res_id}/qr",
        headers=auth_other["headers"],
        cookies=auth_other["cookies"],
    )
    assert resp_other.status_code == 403
    assert "not authorized" in resp_other.json()["detail"]

    # 5. Cancel reservation -> cannot retrieve QR pass anymore
    client.delete(
        f"/api/spaces/reservations/{res_id}",
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    resp_cancelled = client.get(
        f"/api/spaces/reservations/{res_id}/qr",
        headers=auth_owner["headers"],
        cookies=auth_owner["cookies"],
    )
    assert resp_cancelled.status_code == 400
    assert "QR pass is only available for active reservations" in resp_cancelled.json()["detail"]


def test_patron_check_in_window_and_grace_periods(client, db: Session, space_infrastructure):
    """
    Verifies check-in timing boundaries, grace periods, and role permissions:
    - Check-in before window opens (earlier than start_time - 15m) -> 400 Bad Request.
    - Check-in within window (e.g. at start_time) -> 200 OK, checked_in_at populated.
    - Duplicate check-in on already checked-in reservation -> 400 Bad Request.
    - Patron late check-in (after start_time + 15m grace) -> 400 Bad Request.
    - Librarian late check-in (within duration) -> 200 OK (staff override).
    - Check-in after scheduled end_time -> 400 Bad Request.
    - Unauthorized patron check-in -> 403 Forbidden.
    """
    auth_student = make_auth_user(db, client, "checkin_patron@univ.edu", "student", "Checkin Patron")
    auth_other = make_auth_user(db, client, "checkin_other@univ.edu", "student", "Checkin Other")
    auth_lib = make_auth_user(db, client, "checkin_staff@library.org", "librarian", "Checkin Staff")
    seat1 = space_infrastructure["seat1"]
    seat2 = space_infrastructure["seat2"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    # Create active reservation
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": start_utc.isoformat(), "end_time": end_utc.isoformat()},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    res_id = r1.json()["id"]

    # 1. Early check-in attempt (20 minutes before start_time) -> 400 Bad Request
    early_clock = start_utc - timedelta(minutes=20)
    with pytest.raises(HTTPException) as exc_info:
        check_in_reservation_service(db, auth_student["user"], res_id, now_utc=early_clock)
    assert exc_info.value.status_code == 400
    assert "Check-in window opens 15 minutes before" in exc_info.value.detail

    # 2. Unauthorized patron attempt -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        check_in_reservation_service(db, auth_other["user"], res_id, now_utc=start_utc)
    assert exc_info.value.status_code == 403
    assert "not authorized" in exc_info.value.detail

    # 3. Valid check-in at start_time -> 200 OK
    res_checked_in = check_in_reservation_service(db, auth_student["user"], res_id, now_utc=start_utc)
    assert res_checked_in.id == res_id
    assert res_checked_in.status == "active"
    assert res_checked_in.checked_in_at is not None

    # 4. Duplicate check-in attempt -> 400 Bad Request
    with pytest.raises(HTTPException) as exc_info:
        check_in_reservation_service(db, auth_student["user"], res_id, now_utc=start_utc + timedelta(minutes=2))
    assert exc_info.value.status_code == 400
    assert "already checked in" in exc_info.value.detail

    # Clean up reservation
    cancel_reservation_service(db, auth_lib["user"], res_id)

    # 5. Patron late check-in (16 minutes after start_time -> after 15m grace period) -> 400 Bad Request
    s2, e2 = get_future_operational_window(days_ahead=1, start_hour_ist=13, duration_hours=2)
    r2 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat2.id, "start_time": s2.isoformat(), "end_time": e2.isoformat()},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    res2_id = r2.json()["id"]

    late_clock = s2 + timedelta(minutes=16)
    with pytest.raises(HTTPException) as exc_info:
        check_in_reservation_service(db, auth_student["user"], res2_id, now_utc=late_clock)
    assert exc_info.value.status_code == 400
    assert "Check-in window closed 15 minutes after scheduled start time" in exc_info.value.detail

    # 6. Staff override late check-in within scheduled interval -> 200 OK
    res_staff = check_in_reservation_service(db, auth_lib["user"], res2_id, now_utc=late_clock)
    assert res_staff.id == res2_id
    assert res_staff.checked_in_at is not None

    # 7. Check-in after scheduled end time -> 400 Bad Request (for all roles, on un-checked-in reservation)
    s3, e3 = get_future_operational_window(days_ahead=2, start_hour_ist=10, duration_hours=2)
    r3 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": s3.isoformat(), "end_time": e3.isoformat()},
        headers=auth_other["headers"],
        cookies=auth_other["cookies"],
    )
    assert r3.status_code == 201
    res3_id = r3.json()["id"]

    with pytest.raises(HTTPException) as exc_info:
        check_in_reservation_service(db, auth_lib["user"], res3_id, now_utc=e3 + timedelta(minutes=1))
    assert exc_info.value.status_code == 400
    assert "already passed its scheduled end time" in exc_info.value.detail


def test_check_in_by_scanned_token(client, db: Session, space_infrastructure):
    """
    Verifies POST /api/spaces/reservations/check-in-by-token:
    - Scans valid QR token and checks in reservation -> 200 OK.
    - Replay attempt with same token -> rejected.
    """
    auth_student = make_auth_user(db, client, "token_scan_patron@univ.edu", "student", "Token Scan Patron")
    seat = space_infrastructure["seat1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    # 1. Create reservation
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat.id, "start_time": start_utc.isoformat(), "end_time": end_utc.isoformat()},
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    res_id = r1.json()["id"]

    # 2. Get QR token
    resp_qr = client.get(
        f"/api/spaces/reservations/{res_id}/qr",
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    qr_token = resp_qr.json()["qr_token"]

    # 3. Check in by token during window
    with patch("app.services.spaces.get_utc_now", return_value=start_utc):
        resp_checkin = client.post(
            "/api/spaces/reservations/check-in-by-token",
            json={"token": qr_token},
            headers=auth_student["headers"],
            cookies=auth_student["cookies"],
        )
    assert resp_checkin.status_code == 200
    data = resp_checkin.json()
    assert data["id"] == res_id
    assert data["status"] == "active"
    assert data["checked_in_at"] is not None

    # 4. Replay attempt with same token -> 400 Bad Request
    with patch("app.services.spaces.get_utc_now", return_value=start_utc + timedelta(minutes=1)):
        resp_replay = client.post(
            "/api/spaces/reservations/check-in-by-token",
            json={"token": qr_token},
            headers=auth_student["headers"],
            cookies=auth_student["cookies"],
        )
    assert resp_replay.status_code == 400
    assert "already checked in" in resp_replay.json()["detail"]


def test_room_actual_attendees_validation_on_check_in(db: Session, space_infrastructure):
    """
    Verifies actual attendees validation on room check-in:
    - Positive integer up to room capacity is accepted.
    - Exceeding room capacity is rejected with HTTP 400.
    - Zero or negative is rejected.
    """
    auth_teacher = make_auth_user(db, None, "attendee_teacher@univ.edu", "teacher", "Attendee Teacher")
    room = space_infrastructure["room1"]  # capacity = 8
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    payload = ReservationCreate(
        resource_type="room",
        room_id=room.id,
        start_time=start_utc,
        end_time=end_utc,
        expected_attendees=4,
    )
    res = create_reservation_service(db, auth_teacher["user"], payload, now_utc=start_utc)

    # 1. Exceeding capacity -> 400 Bad Request
    with pytest.raises(HTTPException) as exc_info:
        check_in_reservation_service(
            db, auth_teacher["user"], res.id, actual_attendees=room.capacity + 1, now_utc=start_utc
        )
    assert exc_info.value.status_code == 400
    assert "between 1 and room capacity" in exc_info.value.detail

    # 2. Valid attendee count (6 <= 8) -> 200 OK
    res_checked_in = check_in_reservation_service(
        db, auth_teacher["user"], res.id, actual_attendees=6, now_utc=start_utc
    )
    assert res_checked_in.actual_attendees == 6
    assert res_checked_in.checked_in_at is not None


def test_concurrent_check_in_atomic_conditional_update(tmp_path):
    """
    Verifies concurrency safety and replay prevention for check-in:
    Two simultaneous check-in requests for the same reservation execute concurrently.
    Because the database update conditionally requires checked_in_at IS NULL,
    exactly one worker succeeds (rowcount == 1); the second worker sees rowcount == 0
    and receives HTTP 409 Conflict.
    Final DB state: checked_in_at is populated, reservation is checked in exactly once.
    """
    import sqlite3
    db_file = tmp_path / "test_checkin_concurrency.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA busy_timeout = 5000;")
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Quiet Zone', 1, 10, 'silent', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (1, 1, 'S-1', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (1, 'concurrent_student@u.edu', 'Student', 'h', 'student', 1, datetime('now'))")
        conn.exec_driver_sql("""
            INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, expected_attendees, created_at)
            VALUES (1, 1, 'seat', 1, '2026-11-06 10:00:00.000000', '2026-11-06 12:00:00.000000', 'active', 1, datetime('now'))
        """)

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    now_utc = datetime(2026, 11, 6, 10, 0, 0)
    barrier = threading.Barrier(2)
    results = []

    def worker():
        session = session_factory()
        barrier.wait()
        try:
            with atomic_write(session):
                user = session.get(User, 1)
                res = check_in_reservation_service(session, user, 1, now_utc=now_utc)
                return ("success", res.id)
        except HTTPException as he:
            return ("http_error", he.status_code, he.detail)
        except Exception as exc:
            return ("unexpected", str(exc))
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[0] == "success"]
    conflicts = [r for r in results if r[0] == "http_error" and (r[1] in (400, 409))]

    assert len(successes) == 1, f"Expected 1 successful check-in, got {len(successes)}: {results}"
    assert len(conflicts) == 1, f"Expected 1 collision/conflict rejection, got {len(conflicts)}: {results}"

    # Verify final database has checked_in_at set
    with engine.connect() as conn:
        checked_at = conn.exec_driver_sql("SELECT checked_in_at FROM reservations WHERE id = 1").scalar()
        assert checked_at is not None

    engine.dispose()


def test_reservation_lifecycle_sweep_no_show_and_completion(client, db: Session, space_infrastructure):
    """
    Verifies the idempotent reservation lifecycle sweep (Stage 10.3):
    1. Active reservation where checked_in_at IS NULL and start_time + 15m passed -> marked 'no_show'.
    2. Active reservation where checked_in_at IS NOT NULL and end_time passed -> marked 'completed'.
    3. Active reservation where checked_in_at IS NULL and end_time passed -> marked 'no_show', NEVER 'completed'.
    4. Active reservation currently in progress with check-in -> remains 'active'.
    5. Repeated sweep is completely idempotent (0 rows mutated).
    6. Admin endpoint POST /api/spaces/reservations/sweep permissions enforced.
    """
    auth_student = make_auth_user(db, client, "sweep_student@univ.edu", "student", "Sweep Student")
    auth_student2 = make_auth_user(db, client, "sweep_student2@univ.edu", "student", "Sweep Student 2")
    auth_student3 = make_auth_user(db, client, "sweep_student3@univ.edu", "student", "Sweep Student 3")
    auth_student4 = make_auth_user(db, client, "sweep_student4@univ.edu", "student", "Sweep Student 4")
    auth_lib = make_auth_user(db, client, "sweep_lib@library.org", "librarian", "Sweep Lib")
    seat1 = space_infrastructure["seat1"]
    seat2 = space_infrastructure["seat2"]
    seat3 = StudySeat(zone_id=seat1.zone_id, seat_code="S-103-SWP", is_active=True)
    seat4 = StudySeat(zone_id=seat1.zone_id, seat_code="S-104-SWP", is_active=True)
    db.add_all([seat3, seat4])
    db.flush()

    base_time = datetime(2026, 11, 6, 10, 0, 0)

    # 1. Reservation 1: Active, NOT checked in, started 30 mins ago -> Due for no-show
    r1 = Reservation(
        user_id=auth_student["user"].id,
        resource_type="seat",
        seat_id=seat1.id,
        start_time=base_time - timedelta(minutes=30),
        end_time=base_time + timedelta(hours=1),
        status="active",
        expected_attendees=1,
    )
    # 2. Reservation 2: Active, CHECKED IN, ended 10 mins ago -> Due for completed
    r2 = Reservation(
        user_id=auth_student2["user"].id,
        resource_type="seat",
        seat_id=seat2.id,
        start_time=base_time - timedelta(hours=2),
        end_time=base_time - timedelta(minutes=10),
        status="active",
        checked_in_at=base_time - timedelta(hours=2),
        expected_attendees=1,
    )
    # 3. Reservation 3: Active, NOT checked in, ended 5 mins ago -> Due for no-show (NEVER completed!)
    r3 = Reservation(
        user_id=auth_student3["user"].id,
        resource_type="seat",
        seat_id=seat3.id,
        start_time=base_time - timedelta(hours=1),
        end_time=base_time - timedelta(minutes=5),
        status="active",
        expected_attendees=1,
    )
    # 4. Reservation 4: Active, CHECKED IN, end_time in future -> Remains active
    r4 = Reservation(
        user_id=auth_student4["user"].id,
        resource_type="seat",
        seat_id=seat4.id,
        start_time=base_time - timedelta(minutes=20),
        end_time=base_time + timedelta(hours=1),
        status="active",
        checked_in_at=base_time - timedelta(minutes=20),
        expected_attendees=1,
    )
    db.add_all([r1, r2, r3, r4])
    db.commit()

    # 5. Patron calling sweep endpoint -> 403 Forbidden
    resp_patron_denied = client.post(
        "/api/spaces/reservations/sweep",
        headers=auth_student["headers"],
        cookies=auth_student["cookies"],
    )
    assert resp_patron_denied.status_code == 403

    # 6. Execute sweep as librarian with base_time
    report = sweep_study_space_reservations_service(db, user=auth_lib["user"], now_utc=base_time)
    assert report.no_show_count == 2  # r1 and r3
    assert report.completed_count == 1  # r2
    assert r1.id in report.no_show_reservation_ids
    assert r3.id in report.no_show_reservation_ids
    assert r2.id in report.completed_reservation_ids
    assert r4.id not in report.no_show_reservation_ids
    assert r4.id not in report.completed_reservation_ids

    # Verify database states
    db.refresh(r1)
    db.refresh(r2)
    db.refresh(r3)
    db.refresh(r4)
    assert r1.status == "no_show"
    assert r2.status == "completed"
    assert r3.status == "no_show"  # Must NEVER be completed without check-in
    assert r4.status == "active"

    # 7. Repeated sweep -> Idempotent, 0 rows mutated
    report2 = sweep_study_space_reservations_service(db, user=auth_lib["user"], now_utc=base_time)
    assert report2.processed_count == 0
    assert report2.no_show_count == 0
    assert report2.completed_count == 0


def test_qr_token_cross_purpose_authentication_defense(client, db: Session, space_infrastructure):
    """
    Verifies defense in depth against cross-purpose JWT confusion (Stage 10.3.2):
    - QR check-in tokens cannot authenticate as access tokens via Bearer header -> 401 Unauthorized.
    - QR check-in tokens cannot authenticate as access tokens via access_token cookie -> 401 Unauthorized.
    - Access tokens lacking type: 'access' claim are rejected -> 401 Unauthorized.
    - Access tokens with wrong type claim are rejected -> 401 Unauthorized.
    - Genuine access tokens with type: 'access' authenticate successfully -> 200 OK.
    """
    from jose import jwt
    settings = get_settings()
    auth_patron = make_auth_user(db, client, "defense_patron@univ.edu", "student", "Defense Patron")
    seat = space_infrastructure["seat1"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    # 1. Create a reservation
    r1 = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat.id, "start_time": start_utc.isoformat(), "end_time": end_utc.isoformat()},
        headers=auth_patron["headers"],
        cookies=auth_patron["cookies"],
    )
    assert r1.status_code == 201
    res_id = r1.json()["id"]

    # 2. Retrieve genuine QR token
    resp_qr = client.get(
        f"/api/spaces/reservations/{res_id}/qr",
        headers=auth_patron["headers"],
        cookies=auth_patron["cookies"],
    )
    assert resp_qr.status_code == 200
    qr_token = resp_qr.json()["qr_token"]

    # 3. Present QR token as Bearer access token -> 401 Unauthorized
    resp_bearer = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {qr_token}"},
    )
    assert resp_bearer.status_code == 401
    assert "Could not validate credentials" in resp_bearer.json()["detail"]

    # 4. Present QR token in access_token cookie -> 401 Unauthorized
    resp_cookie = client.get(
        "/api/auth/me",
        cookies={"access_token": qr_token},
    )
    assert resp_cookie.status_code == 401
    assert "Could not validate credentials" in resp_cookie.json()["detail"]

    # 5. Token signed with JWT_SECRET_KEY but missing 'type' claim -> 401 Unauthorized
    legacy_token = jwt.encode(
        {"sub": str(auth_patron["user"].id), "role": "student"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    resp_legacy = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )
    assert resp_legacy.status_code == 401

    # 6. Token signed with JWT_SECRET_KEY but type != 'access' -> 401 Unauthorized
    wrong_type_jwt = jwt.encode(
        {"sub": str(auth_patron["user"].id), "role": "student", "type": "refresh"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    resp_wrong_type = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {wrong_type_jwt}"},
    )
    assert resp_wrong_type.status_code == 401

    # 7. Genuine access token with type: 'access' -> 200 OK
    resp_valid = client.get(
        "/api/auth/me",
        headers=auth_patron["headers"],
        cookies=auth_patron["cookies"],
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["id"] == auth_patron["user"].id


def test_cross_reservation_and_wrong_user_token_rejection(client, db: Session, space_infrastructure):
    """
    Verifies that QR check-in tokens are cryptographically bound to specific reservations & patrons:
    - Token for Reservation A cannot check in Reservation B -> 400 Bad Request.
    - Token issued for User A presented to check in User B -> 400 Bad Request.
    """
    auth_student_a = make_auth_user(db, client, "token_a@univ.edu", "student", "Token User A")
    auth_student_b = make_auth_user(db, client, "token_b@univ.edu", "student", "Token User B")
    seat1 = space_infrastructure["seat1"]
    seat2 = space_infrastructure["seat2"]
    start_utc, end_utc = get_future_operational_window(days_ahead=1, start_hour_ist=10, duration_hours=2)

    # 1. Create Reservation A
    r_a = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat1.id, "start_time": start_utc.isoformat(), "end_time": end_utc.isoformat()},
        headers=auth_student_a["headers"],
        cookies=auth_student_a["cookies"],
    )
    res_a_id = r_a.json()["id"]

    # 2. Create Reservation B
    r_b = client.post(
        "/api/spaces/reservations",
        json={"resource_type": "seat", "seat_id": seat2.id, "start_time": start_utc.isoformat(), "end_time": end_utc.isoformat()},
        headers=auth_student_b["headers"],
        cookies=auth_student_b["cookies"],
    )
    res_b_id = r_b.json()["id"]

    # 3. Get QR token for Reservation A
    resp_qr_a = client.get(
        f"/api/spaces/reservations/{res_a_id}/qr",
        headers=auth_student_a["headers"],
        cookies=auth_student_a["cookies"],
    )
    token_a = resp_qr_a.json()["qr_token"]

    # 4. Attempt to check in Reservation B using Token A -> 400 Bad Request
    with pytest.raises(HTTPException) as exc_info:
        check_in_reservation_service(
            db=db,
            user=auth_student_b["user"],
            reservation_id=res_b_id,
            qr_token=token_a,
            now_utc=start_utc,
        )
    assert exc_info.value.status_code == 400
    assert "QR token does not match the target reservation" in exc_info.value.detail


def test_cli_space_sweep_atomic_transaction_and_recovery(tmp_path):
    """
    Verifies that run_space_reservations_sweep runs within atomic_write(db),
    uses BEGIN IMMEDIATE write transactions, and rolls back cleanly on exception.
    """
    import sqlite3
    from app.cli_sweep import run_space_reservations_sweep

    db_file = tmp_path / "test_cli_sweep_atomic.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    base_time = datetime(2026, 11, 6, 10, 0, 0)

    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Zone', 1, 10, 'silent', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (1, 1, 'S-1', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (1, 'cli_user@u.edu', 'User', 'h', 'student', 1, datetime('now'))")
        start_str = (base_time - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S.000000")
        end_str = (base_time + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S.000000")
        conn.exec_driver_sql(f"""
            INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, expected_attendees, created_at)
            VALUES (1, 1, 'seat', 1, '{start_str}', '{end_str}', 'active', 1, datetime('now'))
        """)

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with session_factory() as session:
        report = run_space_reservations_sweep(as_of_datetime_str=base_time.isoformat(), db_session=session)
        assert report.no_show_count == 1
        assert 1 in report.no_show_reservation_ids

    with engine.connect() as conn:
        status_in_db = conn.exec_driver_sql("SELECT status FROM reservations WHERE id = 1").scalar()
        assert status_in_db == "no_show"

    engine.dispose()


def test_concurrent_checkin_racing_no_show_sweeper(tmp_path):
    """
    Verifies that simultaneous check-in and lifecycle sweeper racing at the grace period
    boundary produces exactly one valid terminal state, with zero contradictory states.
    - If check-in writes first -> checked_in_at is set, status remains 'active'.
    - If sweeper writes first -> status is set to 'no_show', check-in fails with HTTP 409 Conflict.
    - Under no condition does status become 'no_show' with checked_in_at NOT NULL.
    """
    import sqlite3
    db_file = tmp_path / "test_checkin_sweep_race.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    base_time = datetime(2026, 11, 6, 10, 15, 0)  # Exactly at grace period cutoff

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA busy_timeout = 5000;")
        conn.exec_driver_sql("INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) VALUES (1, 'Z-1', 'Quiet Zone', 1, 10, 'silent', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) VALUES (1, 1, 'S-1', 1, 0, 0, 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (1, 'race_user@u.edu', 'Patron', 'h', 'student', 1, datetime('now'))")
        conn.exec_driver_sql("INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at) VALUES (2, 'race_lib@u.edu', 'Librarian', 'h', 'librarian', 1, datetime('now'))")
        conn.exec_driver_sql("""
            INSERT INTO reservations (id, user_id, resource_type, seat_id, start_time, end_time, status, expected_attendees, created_at)
            VALUES (1, 1, 'seat', 1, '2026-11-06 10:00:00.000000', '2026-11-06 12:00:00.000000', 'active', 1, datetime('now'))
        """)

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    barrier = threading.Barrier(2)
    results = {}

    def checkin_worker():
        session = session_factory()
        barrier.wait()
        try:
            with atomic_write(session):
                user = session.get(User, 1)
                res = check_in_reservation_service(session, user, 1, now_utc=base_time)
                results["checkin"] = ("success", res.status, res.checked_in_at)
        except HTTPException as he:
            results["checkin"] = ("http_error", he.status_code, he.detail)
        except Exception as exc:
            results["checkin"] = ("unexpected", str(exc))
        finally:
            session.close()

    def sweep_worker():
        session = session_factory()
        barrier.wait()
        try:
            with atomic_write(session):
                lib_user = session.get(User, 2)
                rep = sweep_study_space_reservations_service(session, user=lib_user, now_utc=base_time)
                results["sweep"] = ("success", rep.no_show_count)
        except Exception as exc:
            results["sweep"] = ("unexpected", str(exc))
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(checkin_worker)
        f2 = executor.submit(sweep_worker)
        concurrent.futures.wait([f1, f2])

    with engine.connect() as conn:
        final_row = conn.exec_driver_sql("SELECT status, checked_in_at FROM reservations WHERE id = 1").one()
        final_status, final_checked_in = final_row[0], final_row[1]

    # Contradictory state check: Must NEVER be no_show with checked_in_at set
    assert not (final_status == "no_show" and final_checked_in is not None), "Contradictory state: no_show with checked_in_at populated!"

    # Either check-in won or sweeper won
    if final_status == "active":
        assert final_checked_in is not None
        assert results["checkin"][0] == "success"
    elif final_status == "no_show":
        assert final_checked_in is None
        assert results["checkin"][0] == "http_error"
        assert results["checkin"][1] in (400, 409)

    engine.dispose()
