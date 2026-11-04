"""
Comprehensive automated tests for Stage 10.4: Occupancy Tracking, Telemetry & Analytics.

Tests:
1. Seat occupancy calculation:
   - Checked-in seat reservation counts as 1 occupant.
   - Non-checked-in active reservation excluded.
   - Cancelled, completed, and no-show reservations excluded.
   - Out-of-window reservations excluded.
2. Room occupancy calculation:
   - Uses actual_attendees when available.
   - Falls back to expected_attendees when actual_attendees is None.
   - Clamped to configured room capacity.
3. Total library occupancy and capacity aggregation:
   - Distinguishes seats from rooms.
   - Total occupancy = seats + room attendees.
   - Available capacity = total capacity - occupied.
   - Utilization percentages safely computed and clamped.
4. Edge cases:
   - Empty library (zero reservations) -> 0.0% utilization, no ZeroDivisionError.
   - Missing / inactive resources handled safely.
5. Privacy & authorization:
   - Public/student endpoints expose zero patron identities or user IDs.
   - Telemetry ingestion restricted to librarians and admins (students get 403).
   - Unauthenticated access returns 401.
6. Telemetry ingestion:
   - Valid ingestion computes capacity utilization and records observation.
   - Idempotent duplicate ingestion returns existing record with 'idempotent_duplicate'.
   - Delayed corrected reading updates existing record with 'updated'.
   - Negative headcount rejected (400/422).
   - Non-existent or inactive zone rejected (404/400).
7. Historical aggregation & peak hours:
   - SQL aggregation by day and hour.
   - Peak usage hour (0-23) identification and distribution.
   - Invalid date ranges and intervals rejected (400).
8. Concurrent telemetry writes:
   - Multi-threaded ingestion handles database transactions safely without deadlocks.
"""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import create_access_token, hash_password
from app.database import Base, setup_engine_events
from app.main import app
from app.models import OccupancyObservation, Reservation, StudyRoom, StudySeat, StudyZone, User
from app.services import occupancy as occupancy_service
from app.schemas import TelemetryObservationCreate


# ── Test Infrastructure Fixtures ──────────────────────────────────────────────

@pytest.fixture
def occupancy_env(db: Session):
    """Sets up a complete set of zones, seats, rooms, and users for occupancy tests."""
    # 1. Users (multiple distinct patrons to respect overlap trigger constraints)
    student = User(
        email="occ_student1@library.edu",
        full_name="Alice Student",
        hashed_password=hash_password("StudentPass123!"),
        role="student",
        is_active=True,
    )
    student2 = User(
        email="occ_student2@library.edu",
        full_name="David Student",
        hashed_password=hash_password("StudentPass123!"),
        role="student",
        is_active=True,
    )
    student3 = User(
        email="occ_student3@library.edu",
        full_name="Eva Student",
        hashed_password=hash_password("StudentPass123!"),
        role="student",
        is_active=True,
    )
    teacher = User(
        email="occ_teacher@library.edu",
        full_name="Dr. Bob Teacher",
        hashed_password=hash_password("TeacherPass123!"),
        role="teacher",
        is_active=True,
    )
    librarian = User(
        email="occ_librarian@library.edu",
        full_name="Clara Librarian",
        hashed_password=hash_password("LibrarianPass123!"),
        role="librarian",
        is_active=True,
    )
    db.add_all([student, student2, student3, teacher, librarian])
    db.flush()

    # 2. Zones
    z_quiet = StudyZone(
        zone_code="ZONE-TEST-QUIET",
        name="Quiet Study Zone",
        floor=1,
        total_capacity=10,
        noise_policy="quiet",
        is_active=True,
    )
    z_collab = StudyZone(
        zone_code="ZONE-TEST-COLLAB",
        name="Collaborative Hub",
        floor=2,
        total_capacity=20,
        noise_policy="collaborative",
        is_active=True,
    )
    z_inactive = StudyZone(
        zone_code="ZONE-TEST-INACTIVE",
        name="Renovating Zone",
        floor=3,
        total_capacity=5,
        noise_policy="silent",
        is_active=False,
    )
    db.add_all([z_quiet, z_collab, z_inactive])
    db.flush()

    # 3. Seats (10 in quiet zone, 20 in collab zone)
    seats = []
    for i in range(1, 11):
        seats.append(
            StudySeat(
                zone_id=z_quiet.id,
                seat_code=f"SQ-{i:02d}",
                has_power_outlet=(i % 2 == 1),
                has_monitor=(i % 3 == 0),
                is_accessible=(i == 1),
                is_active=True,
            )
        )
    for i in range(1, 21):
        seats.append(
            StudySeat(
                zone_id=z_collab.id,
                seat_code=f"SC-{i:02d}",
                has_power_outlet=True,
                has_monitor=False,
                is_accessible=False,
                is_active=True,
            )
        )
    db.add_all(seats)
    db.flush()

    # 4. Rooms (2 rooms: cap 8 and cap 12)
    room1 = StudyRoom(
        room_code="ROOM-TEST-101",
        name="Conference Room Alpha",
        capacity=8,
        display_type="projector",
        has_whiteboard=True,
        is_active=True,
    )
    room2 = StudyRoom(
        room_code="ROOM-TEST-102",
        name="Meeting Studio Beta",
        capacity=12,
        display_type="tv",
        has_whiteboard=True,
        is_active=True,
    )
    db.add_all([room1, room2])
    db.flush()

    return {
        "student": student,
        "student2": student2,
        "student3": student3,
        "teacher": teacher,
        "librarian": librarian,
        "z_quiet": z_quiet,
        "z_collab": z_collab,
        "z_inactive": z_inactive,
        "seats": seats,
        "room1": room1,
        "room2": room2,
    }


def auth_headers_for(user: User) -> dict:
    """Generates valid Bearer authentication headers and CSRF tokens for a test user."""
    token = create_access_token(user_id=user.id, role=user.role)
    csrf_val = f"csrf-{user.role}-{user.id}"
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
        "cookies": {"access_token": token, "csrf_token": csrf_val},
    }


# ── 1. Seat Occupancy Live Calculation ────────────────────────────────────────

def test_seat_occupancy_live_calculation(db: Session, occupancy_env: dict):
    env = occupancy_env
    now = datetime(2026, 11, 10, 10, 30, 0)

    seat1 = env["seats"][0]  # quiet zone
    seat2 = env["seats"][1]  # quiet zone
    seat3 = env["seats"][2]  # quiet zone
    seat4 = env["seats"][10] # collab zone

    # 1. Checked-in active reservation (counts as 1 occupant)
    r1 = Reservation(
        user_id=env["student"].id,
        resource_type="seat",
        seat_id=seat1.id,
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(minutes=30),
        status="active",
        checked_in_at=now - timedelta(minutes=25),
        expected_attendees=1,
    )
    # 2. Active reservation WITHOUT check-in (MUST NOT count as occupant)
    r2 = Reservation(
        user_id=env["teacher"].id,
        resource_type="seat",
        seat_id=seat2.id,
        start_time=now - timedelta(minutes=10),
        end_time=now + timedelta(minutes=50),
        status="active",
        checked_in_at=None,
        expected_attendees=1,
    )
    # 3. Cancelled reservation with past check-in (MUST NOT count)
    r3 = Reservation(
        user_id=env["librarian"].id,
        resource_type="seat",
        seat_id=seat3.id,
        start_time=now - timedelta(minutes=45),
        end_time=now + timedelta(minutes=15),
        status="cancelled",
        checked_in_at=now - timedelta(minutes=40),
        expected_attendees=1,
    )
    # 4. Collab zone checked-in seat (counts as 1 occupant in collab zone)
    r4 = Reservation(
        user_id=env["student2"].id,
        resource_type="seat",
        seat_id=seat4.id,
        start_time=now - timedelta(minutes=15),
        end_time=now + timedelta(minutes=45),
        status="active",
        checked_in_at=now - timedelta(minutes=10),
        expected_attendees=1,
    )
    db.add_all([r1, r2, r3, r4])
    db.flush()

    # Calculate live occupancy as of 'now'
    res = occupancy_service.calculate_live_occupancy(db=db, as_of=now)

    # Total occupied seats across library: 2 (r1 in quiet, r4 in collab)
    assert res.occupied_seats == 2
    assert res.seat_utilization_percentage > 0.0

    # Zone breakdown check
    quiet_summary = next(z for z in res.zones if z.zone_id == env["z_quiet"].id)
    assert quiet_summary.occupied_seats == 1
    assert quiet_summary.available_seats == 9
    assert quiet_summary.total_capacity == 10
    assert quiet_summary.utilization_percentage == 10.0

    collab_summary = next(z for z in res.zones if z.zone_id == env["z_collab"].id)
    assert collab_summary.occupied_seats == 1
    assert collab_summary.available_seats == 19
    assert collab_summary.total_capacity == 20
    assert collab_summary.utilization_percentage == 5.0


def test_out_of_window_seat_reservations_excluded(db: Session, occupancy_env: dict):
    env = occupancy_env
    now = datetime(2026, 11, 10, 10, 30, 0)
    seat = env["seats"][0]

    # Future reservation (starts in 30 mins)
    future_r = Reservation(
        user_id=env["student"].id,
        resource_type="seat",
        seat_id=seat.id,
        start_time=now + timedelta(minutes=30),
        end_time=now + timedelta(hours=2),
        status="active",
        checked_in_at=now,
        expected_attendees=1,
    )
    db.add(future_r)
    db.flush()

    res = occupancy_service.calculate_live_occupancy(db=db, as_of=now)
    assert res.occupied_seats == 0


# ── 2. Room Occupancy Using Actual Attendees ──────────────────────────────────

def test_room_occupancy_using_actual_attendees(db: Session, occupancy_env: dict):
    env = occupancy_env
    now = datetime(2026, 11, 10, 14, 0, 0)

    # Room 1 (cap 8): checked-in with actual_attendees=6
    r_room1 = Reservation(
        user_id=env["teacher"].id,
        resource_type="room",
        room_id=env["room1"].id,
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(minutes=60),
        status="active",
        checked_in_at=now - timedelta(minutes=28),
        expected_attendees=4,
        actual_attendees=6,
    )

    # Room 2 (cap 12): checked-in with actual_attendees=None -> fallback to expected_attendees=10
    r_room2 = Reservation(
        user_id=env["student"].id,
        resource_type="room",
        room_id=env["room2"].id,
        start_time=now - timedelta(minutes=15),
        end_time=now + timedelta(minutes=45),
        status="active",
        checked_in_at=now - timedelta(minutes=14),
        expected_attendees=10,
        actual_attendees=None,
    )
    db.add_all([r_room1, r_room2])
    db.flush()

    res = occupancy_service.calculate_live_occupancy(db=db, as_of=now)

    assert res.active_rooms_count == 2
    assert res.total_rooms_count == 2
    # Room attendees = 6 + 10 = 16
    assert res.occupied_room_attendees == 16
    assert res.total_room_capacity == 20  # 8 + 12
    # Utilization: (16 / 20) * 100 = 80.0%
    assert res.room_attendees_utilization_percentage == 80.0


def test_room_occupancy_clamped_to_capacity(db: Session, occupancy_env: dict):
    env = occupancy_env
    now = datetime(2026, 11, 10, 14, 0, 0)

    # Room 1 has capacity 8, but report claimed 15 attendees
    r_room = Reservation(
        user_id=env["teacher"].id,
        resource_type="room",
        room_id=env["room1"].id,
        start_time=now - timedelta(minutes=10),
        end_time=now + timedelta(minutes=50),
        status="active",
        checked_in_at=now - timedelta(minutes=9),
        expected_attendees=8,
        actual_attendees=15,  # Exceeds room capacity
    )
    db.add(r_room)
    db.flush()

    res = occupancy_service.calculate_live_occupancy(db=db, as_of=now)
    # Must be safely clamped to room capacity (8)
    assert res.occupied_room_attendees == 8
    assert res.room_attendees_utilization_percentage == 40.0  # 8 / 20 total room cap


# ── 3. Total Library Occupancy & Capacity Aggregation ─────────────────────────

def test_total_library_occupancy_aggregation(db: Session, occupancy_env: dict):
    env = occupancy_env
    now = datetime(2026, 11, 10, 15, 0, 0)

    # 3 seats checked in by 3 distinct students
    students = [env["student"], env["student2"], env["student3"]]
    r_seats = [
        Reservation(
            user_id=students[i].id,
            resource_type="seat",
            seat_id=env["seats"][i].id,
            start_time=now - timedelta(minutes=20),
            end_time=now + timedelta(minutes=40),
            status="active",
            checked_in_at=now - timedelta(minutes=18),
            expected_attendees=1,
        )
        for i in range(3)
    ]
    # 1 room checked in with 5 attendees
    r_room = Reservation(
        user_id=env["teacher"].id,
        resource_type="room",
        room_id=env["room1"].id,
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(minutes=30),
        status="active",
        checked_in_at=now - timedelta(minutes=25),
        expected_attendees=5,
        actual_attendees=5,
    )
    db.add_all(r_seats + [r_room])
    db.flush()

    res = occupancy_service.calculate_live_occupancy(db=db, as_of=now)

    # Total occupancy = 3 (seats) + 5 (room attendees) = 8
    assert res.total_library_occupancy == 8
    # Total capacity = 30 (seats: 10 + 20) + 20 (rooms: 8 + 12) = 50
    assert res.total_library_capacity == 50
    assert res.total_library_available == 42
    # Overall utilization: (8 / 50) * 100 = 16.0%
    assert res.overall_utilization_percentage == 16.0
    assert res.provenance == "reservation_estimate"


def test_zero_capacity_and_empty_library(db: Session, occupancy_env: dict):
    # No reservations present
    res = occupancy_service.calculate_live_occupancy(db=db)
    assert res.total_library_occupancy == 0
    assert res.overall_utilization_percentage == 0.0
    assert res.total_library_available == res.total_library_capacity
    assert res.active_rooms_count == 0


# ── 4. Privacy & Authorization Checks ─────────────────────────────────────────

def test_public_occupancy_endpoints_privacy(client: TestClient, occupancy_env: dict):
    auth = auth_headers_for(occupancy_env["student"])

    # 1. /api/spaces/occupancy/current
    resp = client.get("/api/spaces/occupancy/current", headers=auth["headers"], cookies=auth["cookies"])
    assert resp.status_code == 200
    data = resp.json()
    # Confirm schema contains high-level metrics without patron identity leaks
    assert "total_library_occupancy" in data
    assert "overall_utilization_percentage" in data
    # Check that no user_id or patron name is returned
    for zone in data["zones"]:
        assert "user_id" not in zone
        assert "student" not in str(zone).lower()
    for room in data["rooms"]:
        assert "user_id" not in room
        assert "student" not in str(room).lower()

    # 2. /api/spaces/occupancy/zones
    resp_zones = client.get("/api/spaces/occupancy/zones", headers=auth["headers"], cookies=auth["cookies"])
    assert resp_zones.status_code == 200
    assert isinstance(resp_zones.json(), list)

    # 3. /api/spaces/occupancy/resources
    resp_res = client.get("/api/spaces/occupancy/resources", headers=auth["headers"], cookies=auth["cookies"])
    assert resp_res.status_code == 200
    res_data = resp_res.json()
    assert "seats" in res_data
    assert "rooms" in res_data
    assert "power_outlet_seats_count" in res_data["seats"]


def test_telemetry_ingestion_role_enforcement(client: TestClient, occupancy_env: dict):
    stud_auth = auth_headers_for(occupancy_env["student"])
    lib_auth = auth_headers_for(occupancy_env["librarian"])
    zone_id = occupancy_env["z_quiet"].id

    payload = {
        "zone_id": zone_id,
        "observed_count": 5,
        "source_sensor_id": "SENSOR-Q-01",
    }

    # Student cannot ingest telemetry -> 403 Forbidden
    resp_stud = client.post(
        "/api/spaces/occupancy/telemetry",
        json=payload,
        headers=stud_auth["headers"],
        cookies=stud_auth["cookies"],
    )
    assert resp_stud.status_code == 403

    # Unauthenticated cannot ingest -> 401 Unauthorized (with valid CSRF token, no auth token)
    csrf_val = "test-csrf-unauth"
    resp_unauth = client.post(
        "/api/spaces/occupancy/telemetry",
        json=payload,
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val},
        cookies={"csrf_token": csrf_val},
    )
    assert resp_unauth.status_code == 401

    # Librarian CAN ingest telemetry -> 201 Created
    resp_lib = client.post(
        "/api/spaces/occupancy/telemetry",
        json=payload,
        headers=lib_auth["headers"],
        cookies=lib_auth["cookies"],
    )
    assert resp_lib.status_code == 201
    created_data = resp_lib.json()
    assert created_data["zone_id"] == zone_id
    assert created_data["observed_count"] == 5
    assert created_data["capacity_utilization"] == 0.5  # 5 / 10 capacity
    assert created_data["status"] == "recorded"


# ── 5. Telemetry Ingestion Validation & Idempotency ───────────────────────────

def test_telemetry_idempotent_duplicate_handling(client: TestClient, occupancy_env: dict):
    auth = auth_headers_for(occupancy_env["librarian"])
    zone_id = occupancy_env["z_quiet"].id
    rec_time = "2026-11-10T09:00:00"

    payload = {
        "zone_id": zone_id,
        "recorded_at": rec_time,
        "observed_count": 4,
        "source_sensor_id": "SENSOR-IDEMP-01",
    }

    # 1. Initial ingestion
    r1 = client.post(
        "/api/spaces/occupancy/telemetry",
        json=payload,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r1.status_code == 201
    assert r1.json()["status"] == "recorded"
    obs_id = r1.json()["id"]

    # 2. Identical duplicate ingestion -> idempotent response with status 'idempotent_duplicate'
    r2 = client.post(
        "/api/spaces/occupancy/telemetry",
        json=payload,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == obs_id
    assert r2.json()["status"] == "idempotent_duplicate"

    # 3. Delayed corrected reading (same zone, same time, count=7) -> status 'updated'
    updated_payload = dict(payload, observed_count=7)
    r3 = client.post(
        "/api/spaces/occupancy/telemetry",
        json=updated_payload,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r3.status_code == 201
    assert r3.json()["id"] == obs_id
    assert r3.json()["status"] == "updated"
    assert r3.json()["observed_count"] == 7
    assert r3.json()["capacity_utilization"] == 0.7


def test_telemetry_invalid_payloads_rejected(client: TestClient, occupancy_env: dict):
    auth = auth_headers_for(occupancy_env["librarian"])

    # 1. Non-existent zone
    r1 = client.post(
        "/api/spaces/occupancy/telemetry",
        json={"zone_id": 9999, "observed_count": 5},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r1.status_code == 404

    # 2. Inactive zone
    r2 = client.post(
        "/api/spaces/occupancy/telemetry",
        json={"zone_id": occupancy_env["z_inactive"].id, "observed_count": 2},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r2.status_code == 400
    assert "inactive" in r2.json()["detail"].lower()

    # 3. Negative observed count
    r3 = client.post(
        "/api/spaces/occupancy/telemetry",
        json={"zone_id": occupancy_env["z_quiet"].id, "observed_count": -3},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r3.status_code in (400, 422)


# ── 6. Historical Aggregation & Peak Usage Analysis ───────────────────────────

def test_historical_occupancy_aggregation(client: TestClient, db: Session, occupancy_env: dict):
    auth = auth_headers_for(occupancy_env["student"])
    zone = occupancy_env["z_quiet"]

    # Seed 4 known historical observations across 3 days
    base_dt = datetime(2026, 11, 1, 10, 0, 0)
    obs_data = [
        OccupancyObservation(
            zone_id=zone.id,
            recorded_at=base_dt,
            observed_count=4,
            capacity_utilization=0.4,
            source_sensor_id="SENSOR-HIST-01",
        ),
        OccupancyObservation(
            zone_id=zone.id,
            recorded_at=base_dt + timedelta(hours=2),
            observed_count=8,
            capacity_utilization=0.8,
            source_sensor_id="SENSOR-HIST-01",
        ),
        OccupancyObservation(
            zone_id=zone.id,
            recorded_at=base_dt + timedelta(days=1, hours=1),
            observed_count=6,
            capacity_utilization=0.6,
            source_sensor_id="SENSOR-HIST-01",
        ),
        OccupancyObservation(
            zone_id=zone.id,
            recorded_at=base_dt + timedelta(days=2),
            observed_count=2,
            capacity_utilization=0.2,
            source_sensor_id="SENSOR-HIST-01",
        ),
    ]
    db.add_all(obs_data)
    db.flush()

    # Daily aggregation
    resp_daily = client.get(
        f"/api/spaces/occupancy/historical?zone_id={zone.id}&interval=day&start_date=2026-11-01T00:00:00&end_date=2026-11-05T00:00:00",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp_daily.status_code == 200
    daily_json = resp_daily.json()
    assert daily_json["total_observations"] == 4
    assert daily_json["overall_peak_occupancy"] == 8
    # Average: (4 + 8 + 6 + 2) / 4 = 5.0
    assert daily_json["overall_avg_occupancy"] == 5.0
    assert len(daily_json["data_points"]) == 3  # 3 distinct days

    # Hourly aggregation
    resp_hourly = client.get(
        f"/api/spaces/occupancy/historical?zone_id={zone.id}&interval=hour&start_date=2026-11-01T00:00:00&end_date=2026-11-01T23:59:59",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp_hourly.status_code == 200
    hourly_json = resp_hourly.json()
    assert hourly_json["total_observations"] == 2
    assert len(hourly_json["data_points"]) == 2


def test_peak_usage_hours_analysis(client: TestClient, db: Session, occupancy_env: dict):
    auth = auth_headers_for(occupancy_env["student"])
    zone = occupancy_env["z_collab"]

    # Seed observations at 14:00 (peak) and 02:00 (trough)
    base_dt = datetime(2026, 11, 1, 0, 0, 0)
    obs = []
    for day in range(5):
        # 14:00 high occupancy
        obs.append(
            OccupancyObservation(
                zone_id=zone.id,
                recorded_at=base_dt + timedelta(days=day, hours=14),
                observed_count=18,
                capacity_utilization=0.9,
                source_sensor_id="SENSOR-PEAK",
            )
        )
        # 02:00 low occupancy
        obs.append(
            OccupancyObservation(
                zone_id=zone.id,
                recorded_at=base_dt + timedelta(days=day, hours=2),
                observed_count=1,
                capacity_utilization=0.05,
                source_sensor_id="SENSOR-PEAK",
            )
        )
    db.add_all(obs)
    db.flush()

    resp = client.get(
        f"/api/spaces/occupancy/peak-hours?zone_id={zone.id}&days_back=10",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["peak_hour"] == 14
    assert data["peak_hour_avg_occupancy"] == 18.0
    assert data["lowest_hour"] == 2

    # Check that 14:00 is marked is_peak = True
    peak_entry = next(h for h in data["hourly_distribution"] if h["hour_of_day"] == 14)
    assert peak_entry["is_peak"] is True

    trough_entry = next(h for h in data["hourly_distribution"] if h["hour_of_day"] == 2)
    assert trough_entry["is_peak"] is False


def test_invalid_historical_query_rejected(client: TestClient, occupancy_env: dict):
    auth = auth_headers_for(occupancy_env["student"])

    # Invalid interval
    r1 = client.get(
        "/api/spaces/occupancy/historical?interval=second",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r1.status_code == 400

    # Inverted date range
    r2 = client.get(
        "/api/spaces/occupancy/historical?start_date=2026-11-10T00:00:00&end_date=2026-11-01T00:00:00",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert r2.status_code == 400


# ── 7. Concurrent Telemetry Writes ────────────────────────────────────────────

def test_concurrent_telemetry_writes(tmp_path: Path):
    """
    Simulates multiple parallel sensor threads posting observations for different intervals.
    Verifies that the telemetry service persists writes without race condition anomalies.
    """
    import sqlite3
    test_db_file = tmp_path / "concurrent_occupancy.db"
    db_url = f"sqlite:///{test_db_file.as_posix()}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(test_db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    SessionTest = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Seed a zone
    with SessionTest() as s:
        z = StudyZone(
            zone_code="ZONE-CONCUR",
            name="Concurrent Zone",
            floor=1,
            total_capacity=50,
            noise_policy="quiet",
            is_active=True,
        )
        s.add(z)
        s.commit()
        zone_id = z.id

    def worker(hour: int):
        with SessionTest() as s:
            payload = TelemetryObservationCreate(
                zone_id=zone_id,
                recorded_at=datetime(2026, 11, 10, hour, 0, 0),
                observed_count=hour * 2,
                source_sensor_id="CONCUR-SENSOR",
            )
            from app.database import atomic_write
            with atomic_write(s):
                res = occupancy_service.ingest_telemetry_observation(db=s, payload=payload)
            return res

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker, h) for h in range(12)]
        results = [f.result() for f in futures]

    assert len(results) == 12
    with SessionTest() as s:
        count = s.execute(select(OccupancyObservation)).scalars().all()
        assert len(count) == 12


def test_concurrent_duplicate_telemetry_deduplication(tmp_path: Path):
    """
    Simulates multiple parallel sensor threads posting IDENTICAL observations
    (same zone_id, same recorded_at, same observed_count) concurrently.
    Verifies that the transactional write serialization ensures deduplication,
    resulting in exactly 1 observation row and idempotent duplicate status.
    """
    import sqlite3
    test_db_file = tmp_path / "concurrent_dedup.db"
    db_url = f"sqlite:///{test_db_file.as_posix()}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    raw_conn = sqlite3.connect(test_db_file)
    raw_conn.execute("PRAGMA journal_mode = WAL;")
    raw_conn.close()

    SessionTest = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionTest() as s:
        z = StudyZone(
            zone_code="ZONE-DEDUP",
            name="Dedup Zone",
            floor=1,
            total_capacity=50,
            noise_policy="quiet",
            is_active=True,
        )
        s.add(z)
        s.commit()
        zone_id = z.id

    target_dt = datetime(2026, 11, 10, 15, 0, 0)

    def duplicate_worker(worker_id: int):
        with SessionTest() as s:
            payload = TelemetryObservationCreate(
                zone_id=zone_id,
                recorded_at=target_dt,
                observed_count=20,
                source_sensor_id="SENSOR-PARALLEL",
            )
            from app.database import atomic_write
            with atomic_write(s):
                res = occupancy_service.ingest_telemetry_observation(db=s, payload=payload)
            return res.status

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(duplicate_worker, i) for i in range(6)]
        statuses = [f.result() for f in futures]

    assert len(statuses) == 6
    # Exactly one thread records, all other concurrent threads receive idempotent_duplicate
    assert "recorded" in statuses
    assert statuses.count("recorded") == 1
    assert statuses.count("idempotent_duplicate") == 5

    with SessionTest() as s:
        rows = s.execute(select(OccupancyObservation)).scalars().all()
        assert len(rows) == 1
        assert rows[0].observed_count == 20
        assert rows[0].zone_id == zone_id

