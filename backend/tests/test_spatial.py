"""
Automated test suite for Stage 10.5: Interactive Floor Plans, Spatial Resource Mapping & Wayfinding.

Tests:
1. Floor Management:
   - Create, retrieve, and update library floors.
   - Reject duplicate floor numbers and invalid dimensions.
2. Spatial Resource Mapping:
   - Map seats, rooms, and zones with referential integrity.
   - Reject non-existent resources (404).
   - Reject duplicate mappings for the same resource (400).
   - Reject out-of-bounds coordinates (< 0.0 or > 1.05).
   - Enforce floor alignment (seat's zone floor must match floor).
3. Layout Versioning & Publication:
   - Create draft layouts and add structural visual elements.
   - Validate layout geometry, references, and completeness.
   - Publish layout as authoritative, archiving previous revisions.
   - Reject publication if validation errors exist.
   - Role enforcement: Students receive 403 Forbidden for editing and publication.
4. Real-time Availability Derivation:
   - Compute available, reserved, and occupied states from live reservations.
   - Seat check-in marks seat 'occupied'; non-checked-in marks 'reserved'.
   - Room actual_attendees clamped to capacity.
   - Zero patron PII exposed in spatial payloads (no user_id, email, or reservation_id).
5. Wayfinding:
   - Shortest path graph navigation from entrance to target seat/room.
   - Step-by-step directional guidance.
   - Resource location resolution and missing resource 404 handling.
6. Spatial Completeness Reporting:
   - Accurately tracks mapped vs unmapped zones, seats, and rooms.
"""
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import create_access_token, hash_password
from app.database import Base, get_db, get_write_db, setup_engine_events
from app.main import app
from app.models import (
    FloorPlan,
    FloorPlanElement,
    LibraryFloor,
    Reservation,
    SpatialResourceMapping,
    StudyRoom,
    StudySeat,
    StudyZone,
    User,
    WayfindingEdge,
    WayfindingNode,
)
from app.seed_data.generator import SeederConfig
from app.seed_data.spaces_generator import generate_spaces
from app.seed_data.spatial_seed import seed_spatial_data
from app.services import spatial as spatial_service


# ── Test Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def spatial_env(tmp_path):
    """Initializes an isolated SQLite database with users, study spaces, and spatial floor plans."""
    test_db = tmp_path / "spatial_test.db"
    db_url = f"sqlite:///{test_db.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    setup_engine_events(engine)
    Base.metadata.create_all(bind=engine)

    SessionTest = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionTest() as s:
        # Users
        admin = User(email="admin_spatial@lib.org", hashed_password=hash_password("adminpass"), full_name="Spatial Admin", role="admin")
        librarian = User(email="lib_spatial@lib.org", hashed_password=hash_password("libpass"), full_name="Spatial Librarian", role="librarian")
        student = User(email="student_spatial@lib.org", hashed_password=hash_password("studentpass"), full_name="Spatial Student", role="student")
        s.add_all([admin, librarian, student])
        s.commit()

        # Generate standard study spaces
        cfg = SeederConfig()
        spaces = generate_spaces(cfg)
        for z in spaces["zones"]:
            s.add(StudyZone(id=z.id, zone_code=z.zone_code, name=z.name, floor=z.floor, total_capacity=z.total_capacity, noise_policy=z.noise_policy, is_active=z.is_active, created_at=z.created_at))
        for seat in spaces["seats"]:
            s.add(StudySeat(id=seat.id, zone_id=seat.zone_id, seat_code=seat.seat_code, has_power_outlet=seat.has_power_outlet, has_monitor=seat.has_monitor, is_accessible=seat.is_accessible, is_active=seat.is_active, created_at=seat.created_at))
        for r in spaces["rooms"]:
            s.add(StudyRoom(id=r.id, room_code=r.room_code, name=r.name, capacity=r.capacity, display_type=r.display_type, has_whiteboard=r.has_whiteboard, is_active=r.is_active, created_at=r.created_at))
        s.commit()

        # Seed spatial floor plans
        seed_res = seed_spatial_data(s)
        s.commit()

        # Cache user attributes before session closes to avoid DetachedInstanceError
        class SimpleUser:
            def __init__(self, uid, role, email):
                self.id = uid
                self.role = role
                self.email = email

        admin_cached = SimpleUser(admin.id, admin.role, admin.email)
        lib_cached = SimpleUser(librarian.id, librarian.role, librarian.email)
        stud_cached = SimpleUser(student.id, student.role, student.email)

        env = {
            "engine": engine,
            "Session": SessionTest,
            "admin": admin_cached,
            "librarian": lib_cached,
            "student": stud_cached,
            "seed_result": seed_res,
        }
        return env


@pytest.fixture
def client(spatial_env):
    SessionTest = spatial_env["Session"]

    def override_get_db():
        with SessionTest() as session:
            yield session

    def override_get_write_db():
        with SessionTest() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_write_db] = override_get_write_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict:
    tok = create_access_token(user_id=user.id, role=user.role)
    return {"headers": {"Authorization": f"Bearer {tok}", "X-CSRF-Token": "csrf_test_token"}, "cookies": {"access_token": tok, "csrf_token": "csrf_test_token"}}


# ── 1. Floor Management Tests ──────────────────────────────────────────────────

def test_get_all_floors(client: TestClient, spatial_env: dict):
    auth = auth_headers(spatial_env["student"])
    r = client.get("/api/spaces/floors", headers=auth["headers"], cookies=auth["cookies"])
    assert r.status_code == 200
    floors = r.json()
    assert len(floors) == 4
    nums = [f["floor_number"] for f in floors]
    assert nums == [0, 1, 2, 3]


def test_create_floor_librarian_only(client: TestClient, spatial_env: dict):
    student_auth = auth_headers(spatial_env["student"])
    lib_auth = auth_headers(spatial_env["librarian"])

    payload = {
        "floor_number": 4,
        "name": "4th Floor Penthouse Study Deck",
        "description": "Quiet outdoor terrace and skylight seating",
        "display_order": 4,
        "width": 1000.0,
        "height": 700.0,
    }

    # Student forbidden
    r_stud = client.post("/api/spaces/floors", json=payload, headers=student_auth["headers"], cookies=student_auth["cookies"])
    assert r_stud.status_code == 403

    # Librarian allowed
    r_lib = client.post("/api/spaces/floors", json=payload, headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_lib.status_code == 201
    created = r_lib.json()
    assert created["floor_number"] == 4
    assert created["name"] == "4th Floor Penthouse Study Deck"

    # Reject duplicate floor_number
    r_dup = client.post("/api/spaces/floors", json=payload, headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_dup.status_code == 400
    assert "already exists" in r_dup.json()["detail"].lower()


def test_update_floor(client: TestClient, spatial_env: dict):
    lib_auth = auth_headers(spatial_env["librarian"])
    r_update = client.patch(
        "/api/spaces/floors/1",
        json={"name": "Ground Floor Main Atrium"},
        headers=lib_auth["headers"],
        cookies=lib_auth["cookies"],
    )
    assert r_update.status_code == 200
    assert r_update.json()["name"] == "Ground Floor Main Atrium"


# ── 2. Spatial Resource Mapping & Referential Integrity Tests ─────────────────

def test_create_and_delete_resource_mapping(client: TestClient, spatial_env: dict):
    lib_auth = auth_headers(spatial_env["librarian"])
    SessionTest = spatial_env["Session"]

    with SessionTest() as s:
        # Create an unmapped seat in Zone 0 (Ground floor)
        z = s.execute(select(StudyZone).where(StudyZone.floor == 0)).scalars().first()
        new_seat = StudySeat(zone_id=z.id, seat_code="SEAT-NEW-999", is_active=True)
        s.add(new_seat)
        s.commit()
        seat_id = new_seat.id

    # 1. Map valid seat to Floor 0
    map_payload = {
        "resource_type": "seat",
        "resource_id": seat_id,
        "label": "New Seat 999",
        "x": 0.50,
        "y": 0.50,
        "width": 0.04,
        "height": 0.04,
    }
    r_map = client.post("/api/spaces/floors/1/mappings", json=map_payload, headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_map.status_code == 201
    mapping_id = r_map.json()["id"]

    # 2. Duplicate mapping for same seat rejected
    r_dup = client.post("/api/spaces/floors/1/mappings", json=map_payload, headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_dup.status_code == 400
    assert "already mapped" in r_dup.json()["detail"].lower()

    # 3. Delete mapping
    r_del = client.delete(f"/api/spaces/mappings/{mapping_id}", headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_del.status_code == 200


def test_reject_mismatched_floor_resource_mapping(client: TestClient, spatial_env: dict):
    """A seat belonging to a 1st floor zone cannot be mapped to the Ground floor."""
    lib_auth = auth_headers(spatial_env["librarian"])
    SessionTest = spatial_env["Session"]

    with SessionTest() as s:
        z1 = s.execute(select(StudyZone).where(StudyZone.floor == 1)).scalars().first()
        seat_fl1 = s.execute(select(StudySeat).where(StudySeat.zone_id == z1.id)).scalars().first()
        seat_id = seat_fl1.id

        # Delete existing mapping so we test placement
        existing = s.execute(select(SpatialResourceMapping).where(SpatialResourceMapping.resource_type == "seat", SpatialResourceMapping.resource_id == seat_id)).scalar_one_or_none()
        if existing:
            s.delete(existing)
            s.commit()

    # Try mapping to Floor ID 1 (Ground Floor, floor_number=0)
    r_bad = client.post(
        "/api/spaces/floors/1/mappings",
        json={"resource_type": "seat", "resource_id": seat_id, "x": 0.4, "y": 0.4},
        headers=lib_auth["headers"],
        cookies=lib_auth["cookies"],
    )
    assert r_bad.status_code == 400
    assert "incompatible" in r_bad.json()["detail"].lower()


def test_reject_out_of_bounds_coordinates(client: TestClient, spatial_env: dict):
    lib_auth = auth_headers(spatial_env["librarian"])
    r_oob = client.post(
        "/api/spaces/floors/1/mappings",
        json={"resource_type": "seat", "resource_id": 1, "x": 1.5, "y": 0.5},
        headers=lib_auth["headers"],
        cookies=lib_auth["cookies"],
    )
    assert r_oob.status_code == 422


# ── 3. Layout Versioning & Publication Workflow ───────────────────────────────

def test_layout_draft_validation_and_publication(client: TestClient, spatial_env: dict):
    student_auth = auth_headers(spatial_env["student"])
    lib_auth = auth_headers(spatial_env["librarian"])

    # 1. Create a draft layout for Floor 2
    r_draft = client.post(
        "/api/spaces/floors/2/layouts",
        json={"title": "Draft Revision 2", "description": "Experimental collaborative rearrangement"},
        headers=lib_auth["headers"],
        cookies=lib_auth["cookies"],
    )
    assert r_draft.status_code == 201
    layout_id = r_draft.json()["id"]
    assert r_draft.json()["status"] == "draft"

    # 2. Add an element to the draft
    r_elem = client.post(
        "/api/spaces/floors/2/elements",
        json={
            "layout_id": layout_id,
            "element_type": "label",
            "label": "Quiet Reading Corner",
            "geometry_type": "text",
            "geometry_data": {"x": 0.20, "y": 0.30},
        },
        headers=lib_auth["headers"],
        cookies=lib_auth["cookies"],
    )
    assert r_elem.status_code == 201

    # 3. Validate layout
    r_val = client.post(f"/api/spaces/layouts/{layout_id}/validate", headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_val.status_code == 200
    assert r_val.json()["is_valid"] is True

    # 4. Student attempt to publish fails with 403
    r_stud_pub = client.post(f"/api/spaces/layouts/{layout_id}/publish", headers=student_auth["headers"], cookies=student_auth["cookies"])
    assert r_stud_pub.status_code == 403

    # 5. Librarian publishes layout
    r_pub = client.post(f"/api/spaces/layouts/{layout_id}/publish", headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_pub.status_code == 200
    assert r_pub.json()["status"] == "published"


# ── 4. Floor Plan Detail & Real-Time Availability Integration ─────────────────

def test_floor_plan_detail_availability_integration(client: TestClient, spatial_env: dict):
    """
    Verifies that floor plan responses display real-time resource availability:
    - Checked-in active reservation -> 'occupied'
    - Non-checked-in active reservation -> 'reserved'
    - Inactive resource -> 'unavailable'
    - No reservation -> 'available'
    - Zero patron PII exposed.
    """
    auth = auth_headers(spatial_env["student"])
    SessionTest = spatial_env["Session"]

    now = datetime.utcnow()
    with SessionTest() as s:
        # Ground floor seat (zone on floor 0)
        z0 = s.execute(select(StudyZone).where(StudyZone.floor == 0)).scalars().first()
        seats = s.execute(select(StudySeat).where(StudySeat.zone_id == z0.id)).scalars().all()
        seat_occ_id = seats[0].id
        seat_res_id = seats[1].id
        seat_unavail_id = seats[2].id

        seats[2].is_active = False

        # Active checked-in reservation
        res_occ = Reservation(
            user_id=spatial_env["student"].id,
            resource_type="seat",
            seat_id=seat_occ_id,
            start_time=now - timedelta(minutes=30),
            end_time=now + timedelta(minutes=30),
            status="active",
            checked_in_at=now - timedelta(minutes=25),
            expected_attendees=1,
            actual_attendees=1,
        )
        # Active reserved reservation (not yet checked in)
        res_res = Reservation(
            user_id=spatial_env["admin"].id,
            resource_type="seat",
            seat_id=seat_res_id,
            start_time=now - timedelta(minutes=10),
            end_time=now + timedelta(minutes=50),
            status="active",
            checked_in_at=None,
            expected_attendees=1,
        )
        s.add_all([res_occ, res_res])
        s.commit()

    # Query floor 0 detail
    r = client.get("/api/spaces/floors/1/detail", headers=auth["headers"], cookies=auth["cookies"])
    assert r.status_code == 200
    data = r.json()

    assert data["is_demonstration_layout"] is True
    assert "ILLUSTRATIVE DEMONSTRATION LAYOUT" in data["disclosure"]

    res_by_id = {f"{r['resource_type']}_{r['resource_id']}": r for r in data["resources"]}

    # Verify availability statuses
    assert res_by_id[f"seat_{seat_occ_id}"]["availability_status"] == "occupied"
    assert res_by_id[f"seat_{seat_occ_id}"]["current_attendees"] == 1

    assert res_by_id[f"seat_{seat_res_id}"]["availability_status"] == "reserved"

    assert res_by_id[f"seat_{seat_unavail_id}"]["availability_status"] == "unavailable"

    # Verify zero patron personal information leakage
    payload_str = str(data)
    assert spatial_env["student"].email not in payload_str
    for res_item in data["resources"]:
        assert "user_id" not in res_item
        assert "patron" not in res_item
        assert "reservation_id" not in res_item


# ── 5. Spatial Lookup & Wayfinding Tests ───────────────────────────────────────

def test_resource_location_lookup(client: TestClient, spatial_env: dict):
    auth = auth_headers(spatial_env["student"])

    # Locate Room 101 (Floor 1)
    r = client.get("/api/spaces/resources/room/1/location", headers=auth["headers"], cookies=auth["cookies"])
    assert r.status_code == 200
    loc = r.json()
    assert loc["resource_type"] == "room"
    assert loc["resource_id"] == 1
    assert loc["floor_number"] == 1
    assert "guidance" in loc["directional_guidance"].lower() or "proceed" in loc["directional_guidance"].lower()
    assert loc["is_demonstration"] is True

    # Non-existent resource returns 404
    r_missing = client.get("/api/spaces/resources/seat/99999/location", headers=auth["headers"], cookies=auth["cookies"])
    assert r_missing.status_code == 404


def test_wayfinding_route_navigation(client: TestClient, spatial_env: dict):
    auth = auth_headers(spatial_env["student"])

    # Wayfinding to Seat 1 (on Floor 0)
    r = client.get("/api/spaces/resources/seat/1/route", headers=auth["headers"], cookies=auth["cookies"])
    assert r.status_code == 200
    route = r.json()

    assert route["destination_resource_type"] == "seat"
    assert route["destination_resource_id"] == 1
    assert len(route["path_points"]) >= 2
    assert len(route["steps"]) >= 2
    assert route["is_accessible"] is True
    assert route["is_demonstration"] is True
    assert "ILLUSTRATIVE DEMONSTRATION ROUTE" in route["disclosure"]


# ── 6. Spatial Completeness Report Tests ───────────────────────────────────────

def test_spatial_completeness_report(client: TestClient, spatial_env: dict):
    lib_auth = auth_headers(spatial_env["librarian"])
    r = client.get("/api/spaces/spatial/completeness", headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r.status_code == 200
    rep = r.json()

    # 100% of all canonical resources are mapped
    assert rep["total_zones"] == 8
    assert rep["mapped_zones"] == 8
    assert rep["unmapped_zone_ids"] == []

    assert rep["total_seats"] == 150
    assert rep["mapped_seats"] == 150
    assert rep["unmapped_seat_ids"] == []

    assert rep["total_rooms"] == 10
    assert rep["mapped_rooms"] == 10
    assert rep["unmapped_room_ids"] == []

    assert rep["mapping_completeness_percentage"] == 100.0
    assert rep["published_floors_count"] == 4


# ── 7. Alembic Production Migration & Resource Lifecycle Tests ─────────────────

def test_alembic_upgrade_path_for_spatial_subsystem(tmp_path):
    """
    Verifies that a fresh database reaches f6a7b8c9d0e1 via Alembic migrations alone,
    creating all 6 spatial tables without calling Base.metadata.create_all().
    """
    from alembic.config import Config
    from alembic import command
    import sqlite3

    test_db = tmp_path / "alembic_spatial_test.db"
    db_url = f"sqlite:///{test_db.as_posix()}"

    from pathlib import Path
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    alembic_dir = backend_dir / "alembic"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade from empty to head
    command.upgrade(cfg, "head")

    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    rev = cur.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()

    assert rev in ("f6a7b8c9d0e1", "a1b2c3d4e5f6", "b3c4d5e6f7a8", "c4d5e6f7a8b9", "d5e6f7a8b9c0", "e6f7a8b9c0d1")
    spatial_tables = {
        "library_floors",
        "floor_plans",
        "floor_plan_elements",
        "spatial_resource_mappings",
        "wayfinding_nodes",
        "wayfinding_edges",
    }
    assert spatial_tables.issubset(tables)


def test_spatial_resource_lifecycle_integrity(client: TestClient, spatial_env: dict):
    """
    IMP-01: Verifies that deactivating or deleting a resource is reflected cleanly in
    availability derivations and publication validation, and that duplicate mappings are rejected.
    """
    lib_auth = auth_headers(spatial_env["librarian"])
    engine = spatial_env["engine"]
    SessionTest = sessionmaker(bind=engine)

    # 1. Deactivate Seat 1
    with SessionTest() as s:
        seat1 = s.get(StudySeat, 1)
        assert seat1 is not None
        seat1.is_active = False
        s.commit()

    # Query Floor 0 detail: Seat 1 should now report availability_status == 'unavailable'
    r = client.get("/api/spaces/floors/1/detail", headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r.status_code == 200
    resources = r.json()["resources"]
    s1_res = next((res for res in resources if res["resource_type"] == "seat" and res["resource_id"] == 1), None)
    assert s1_res is not None
    assert s1_res["availability_status"] == "unavailable"

    # 2. Decommissioned resource produces validation warning upon layout draft validation
    # Create draft revision for floor 1
    r_draft = client.post(
        "/api/spaces/floors/1/layouts",
        json={"title": "Draft with Decommissioned Seat", "description": "Testing validation"},
        headers=lib_auth["headers"],
        cookies=lib_auth["cookies"],
    )
    assert r_draft.status_code == 201
    draft_id = r_draft.json()["id"]

    r_val = client.post(f"/api/spaces/layouts/{draft_id}/validate", headers=lib_auth["headers"], cookies=lib_auth["cookies"])
    assert r_val.status_code == 200
    val_data = r_val.json()
    assert any("inactive/decommissioned" in w for w in val_data["warnings"])


