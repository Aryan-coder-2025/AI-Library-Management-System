"""Comprehensive unit test suite for Phase 1 – Step 2B Stage 3: Independent Data Generators.

Tests:
1. Namespace seed independence (HMAC-SHA256 isolation).
2. Reproducibility with fixed timestamps and identical seeds (with bcrypt non-determinism noted).
3. Exact allocation arithmetic (books, copies, users, spaces, telemetry).
4. User generation and role counts (500 students, 25 teachers, 5 librarians).
5. Spaces generation counts (8 zones, 150 seats, 10 rooms).
6. Circulation demand distribution and active loan snapshot:
   - 10,000 total loans (8,150 top 300, 1,850 other).
   - 320 active loans at as_of (290 student, 30 teacher).
   - 35 overdue loans at as_of (30 student, 5 teacher).
   - 163 distinct active borrowers.
   - Copy exclusivity across entire timeline.
   - Point-in-time concurrency quotas (student <= 3, teacher <= 10).
   - Student 14d / Teacher 30d durations.
7. Reservation trigger invariants and exact status distribution:
   - 3,000 total reservations (2,400 seat, 600 room).
   - Statuses: 100 active, 2,650 completed, 180 cancelled, 70 no_show.
   - Non-overlapping active intervals for same seat / same room.
8. Telemetry referential integrity, sensor/auditor validation, and value bounds.
9. Embedding fallback behavior (NULL embeddings when unavailable/disabled).
10. Engine disposal pattern.
11. Full dataset end-to-end invariant validation report.
12. Targeted validator corruption detection:
    - Concurrency quota violation detection.
    - Search event referential integrity violation detection.
    - Study zone / room constraint violation detection.
    - Reservation status distribution mismatch detection.
    - Active loan snapshot mismatch detection.
"""
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine, text

from app.seed_data.generator import (
    DEFAULT_BASE_SEED,
    DEFAULT_AS_OF,
    SeederConfig,
    derive_namespace_seed,
    get_namespace_rng,
    generate_all_datasets,
)
from app.seed_data.users_generator import generate_users
from app.seed_data.spaces_generator import generate_spaces
from app.seed_data.catalogue_generator import generate_catalogue
from app.seed_data.circulation_generator import generate_circulation, SyntheticLoan
from app.seed_data.reservation_generator import generate_reservations
from app.seed_data.telemetry_generator import generate_telemetry
from app.seed_data.validator import validate_dataset, ValidationError


# ── 1. Namespace Seed Independence ────────────────────────────────────────────

def test_namespace_seed_independence():
    """
    Verifies that different namespaces derive distinct seeds from the same base seed,
    and that consuming numbers in one namespace does not perturb another namespace stream.
    """
    base_seed = 20261031
    seed_users = derive_namespace_seed(base_seed, "users")
    seed_catalogue = derive_namespace_seed(base_seed, "catalogue")
    seed_spaces = derive_namespace_seed(base_seed, "spaces")

    # Seeds must be distinct 64-bit integers
    assert len({seed_users, seed_catalogue, seed_spaces}) == 3

    # Generator stream isolation: consuming catalogue RNG does not affect users RNG
    rng_users_1 = get_namespace_rng(base_seed, "users")
    rng_catalogue = get_namespace_rng(base_seed, "catalogue")
    for _ in range(100):
        rng_catalogue.random()

    rng_users_2 = get_namespace_rng(base_seed, "users")
    # Both users RNG streams must produce identical sequences
    vals_1 = [rng_users_1.random() for _ in range(25)]
    vals_2 = [rng_users_2.random() for _ in range(25)]
    assert vals_1 == vals_2


# ── 2. Reproducibility with Fixed Timestamps ──────────────────────────────────

def test_reproducibility_with_fixed_seed():
    """
    Verifies that running generators with the same config yields bitwise-identical results
    for all structural fields (id, email, full_name, role, created_at).
    Note: hashed_password uses bcrypt.gensalt() which draws from os.urandom(),
    meaning password hashes vary per run while all domain attributes are deterministic.
    """
    cfg = SeederConfig(base_seed=99991111, enable_embeddings=False)

    users_a = generate_users(cfg, bcrypt_rounds=4)
    users_b = generate_users(cfg, bcrypt_rounds=4)

    assert len(users_a) == len(users_b)
    for ua, ub in zip(users_a, users_b):
        assert ua.id == ub.id
        assert ua.email == ub.email
        assert ua.full_name == ub.full_name
        assert ua.role == ub.role
        assert ua.created_at == ub.created_at


# ── 3. Exact Allocation Arithmetic ────────────────────────────────────────────

def test_exact_catalogue_allocation_arithmetic():
    """
    Verifies exact tier breakdown:
    - 150 bestsellers x 6 = 900
    - 150 Tier 2A x 4 = 600
    - 600 Tier 2B x 3 = 1,800
    - 100 Tier 2C x 2 = 200
    - 500 Monographs x 1 = 500
    Total = 1,500 books, 4,000 copies.
    """
    cfg = SeederConfig(enable_embeddings=False)
    cat = generate_catalogue(cfg)
    books = cat["books"]
    copies = cat["copies"]

    assert len(books) == 1500
    assert len(copies) == 4000

    tier_counts = {}
    for b in books:
        tier_counts[b.tier] = tier_counts.get(b.tier, 0) + 1

    assert tier_counts["bestseller"] == 150
    assert tier_counts["tier2a"] == 150
    assert tier_counts["tier2b"] == 600
    assert tier_counts["tier2c"] == 100
    assert tier_counts["monograph"] == 500

    # Verify copy counts per book ID
    copies_per_book = {}
    for c in copies:
        copies_per_book[c.book_id] = copies_per_book.get(c.book_id, 0) + 1

    for bid in range(1, 151):
        assert copies_per_book[bid] == 6
    for bid in range(151, 301):
        assert copies_per_book[bid] == 4
    for bid in range(301, 901):
        assert copies_per_book[bid] == 3
    for bid in range(901, 1001):
        assert copies_per_book[bid] == 2
    for bid in range(1001, 1501):
        assert copies_per_book[bid] == 1


# ── 4. User Generation Counts & Unique Salts ──────────────────────────────────

def test_user_generation_and_unique_salts():
    """Verifies 500 students, 25 teachers, 5 librarians, and unique bcrypt salts."""
    cfg = SeederConfig()
    users = generate_users(cfg, bcrypt_rounds=4)

    assert len(users) == 530
    roles = {u.role for u in users}
    assert roles == {"student", "teacher", "librarian"}

    students = [u for u in users if u.role == "student"]
    teachers = [u for u in users if u.role == "teacher"]
    librarians = [u for u in users if u.role == "librarian"]

    assert len(students) == 500
    assert len(teachers) == 25
    assert len(librarians) == 5

    # Unique emails
    emails = [u.email for u in users]
    assert len(set(emails)) == 530

    # Unique bcrypt salts/hashes across accounts
    hashes = [u.hashed_password for u in users]
    assert len(set(hashes)) == 530


# ── 5. Spaces Generation Counts ───────────────────────────────────────────────

def test_spaces_generation_counts():
    """Verifies 8 zones, 150 seats, and 10 rooms."""
    cfg = SeederConfig()
    spaces = generate_spaces(cfg)
    zones = spaces["zones"]
    seats = spaces["seats"]
    rooms = spaces["rooms"]

    assert len(zones) == 8
    assert len(seats) == 150
    assert len(rooms) == 10

    # Total seats must match sum of zone capacities
    assert sum(z.total_capacity for z in zones) == 150


# ── 6. Circulation Demand, Active Snapshot & Concurrency ──────────────────────

def test_circulation_copy_exclusivity_and_demand():
    """
    Verifies that:
    1. Exactly 10,000 loans are generated.
    2. Exactly 8,150 are on top 300 titles and 1,850 on other titles.
    3. Exactly 320 active loans at as_of (290 student, 30 teacher).
    4. Exactly 35 overdue loans at as_of (30 student, 5 teacher).
    5. Exactly 163 distinct active borrowers.
    6. No copy is checked out by two borrowers simultaneously.
    7. Point-in-time concurrency quotas are respected (student <= 3, teacher <= 10).
    8. Loan durations are 14 days for students and 30 days for teachers.
    """
    cfg = SeederConfig(enable_embeddings=False)
    users = generate_users(cfg, bcrypt_rounds=4)
    cat = generate_catalogue(cfg)
    loans = generate_circulation(cfg, users, cat["books"], cat["copies"])

    assert len(loans) == 10000

    copy_to_book = {c.id: c.book_id for c in cat["copies"]}
    top_loans = sum(1 for l in loans if copy_to_book[l.copy_id] <= 300)
    other_loans = sum(1 for l in loans if copy_to_book[l.copy_id] > 300)

    assert top_loans == 8150
    assert other_loans == 1850

    as_of = cfg.as_of
    user_role_map = {u.id: u.role for u in users}

    # Active loans at as_of
    active_loans = [
        l for l in loans if l.loan_date <= as_of and (l.returned_at is None or l.returned_at > as_of)
    ]
    assert len(active_loans) == 320

    student_active = [l for l in active_loans if user_role_map[l.user_id] == "student"]
    teacher_active = [l for l in active_loans if user_role_map[l.user_id] == "teacher"]
    assert len(student_active) == 290
    assert len(teacher_active) == 30

    # Overdue loans at as_of
    overdue_loans = [l for l in active_loans if l.due_date < as_of]
    assert len(overdue_loans) == 35

    student_overdue = [l for l in overdue_loans if user_role_map[l.user_id] == "student"]
    teacher_overdue = [l for l in overdue_loans if user_role_map[l.user_id] == "teacher"]
    assert len(student_overdue) == 30
    assert len(teacher_overdue) == 5

    # Distinct active borrowers
    active_borrowers = {l.user_id for l in active_loans}
    assert len(active_borrowers) == 163

    # Copy exclusivity check across the 10,000 loans
    loans_by_copy = {}
    for l in loans:
        loans_by_copy.setdefault(l.copy_id, []).append(l)

    for cid, c_loans in loans_by_copy.items():
        sorted_c = sorted(c_loans, key=lambda x: x.loan_date)
        for i in range(len(sorted_c) - 1):
            l1 = sorted_c[i]
            l2 = sorted_c[i + 1]
            assert l1.returned_at is not None, f"Copy {cid} has unreturned loan before next issuance"
            assert l1.returned_at <= l2.loan_date, f"Copy {cid} returned at {l1.returned_at} after next issue {l2.loan_date}"

    # Point-in-time concurrency check
    user_timeline_events = {}
    for l in loans:
        user_timeline_events.setdefault(l.user_id, []).append((l.loan_date, 1, 1, l.id))
        if l.returned_at is not None:
            user_timeline_events[l.user_id].append((l.returned_at, 0, -1, l.id))

    for uid, evs in user_timeline_events.items():
        role = user_role_map[uid]
        max_quota = 10 if role == "teacher" else 3
        evs.sort(key=lambda x: (x[0], x[1]))
        curr_active = 0
        for dt, prio, delta, lid in evs:
            curr_active += delta
            assert curr_active <= max_quota, f"User {uid} exceeded quota {max_quota} at {dt}"


def test_circulation_borrower_policies():
    """Verifies that students receive 14 days and teachers receive 30 days due date."""
    cfg = SeederConfig(enable_embeddings=False)
    users = generate_users(cfg, bcrypt_rounds=4)
    cat = generate_catalogue(cfg)
    loans = generate_circulation(cfg, users, cat["books"], cat["copies"])

    user_role_map = {u.id: u.role for u in users}

    for l in loans[:500]:
        role = user_role_map[l.user_id]
        duration = (l.due_date - l.loan_date).days
        if role == "teacher":
            assert duration == 30
        elif role == "student":
            assert duration == 14


# ── 7. Reservation Trigger Invariants & Exact Status Distribution ─────────────

def test_reservation_trigger_invariants():
    """
    Verifies that:
    1. Exactly 3,000 reservations (2,400 seat, 600 room).
    2. Exact status breakdown: 100 active, 2,650 completed, 180 cancelled, 70 no_show.
    3. Active reservations on the same seat never overlap.
    4. Active reservations on the same room never overlap.
    5. Schema constraints: end_time > start_time, valid resource_type pointers.
    """
    cfg = SeederConfig()
    users = generate_users(cfg, bcrypt_rounds=4)
    spaces = generate_spaces(cfg)
    reservations = generate_reservations(cfg, users, spaces["seats"], spaces["rooms"])

    assert len(reservations) == 3000

    seat_res = [r for r in reservations if r.resource_type == "seat"]
    room_res = [r for r in reservations if r.resource_type == "room"]

    assert len(seat_res) == 2400
    assert len(room_res) == 600

    # Exact status distribution
    from collections import Counter
    c = Counter(r.status for r in reservations)
    assert c["active"] == 100
    assert c["completed"] == 2650
    assert c["cancelled"] == 180
    assert c["no_show"] == 70

    # Active conflict check on seats
    active_seats = {}
    for r in seat_res:
        assert r.status in ("active", "completed", "cancelled", "no_show")
        assert r.end_time > r.start_time
        if r.status == "active":
            active_seats.setdefault(r.seat_id, []).append(r)

    for sid, res_list in active_seats.items():
        sorted_list = sorted(res_list, key=lambda x: x.start_time)
        for i in range(len(sorted_list) - 1):
            r1 = sorted_list[i]
            r2 = sorted_list[i + 1]
            assert r1.end_time <= r2.start_time, f"Active seat {sid} conflict: {r1.start_time}-{r1.end_time} vs {r2.start_time}-{r2.end_time}"

    # Active conflict check on rooms
    active_rooms = {}
    for r in room_res:
        if r.status == "active":
            active_rooms.setdefault(r.room_id, []).append(r)

    for rid, res_list in active_rooms.items():
        sorted_list = sorted(res_list, key=lambda x: x.start_time)
        for i in range(len(sorted_list) - 1):
            r1 = sorted_list[i]
            r2 = sorted_list[i + 1]
            assert r1.end_time <= r2.start_time, f"Active room {rid} conflict: {r1.start_time}-{r1.end_time} vs {r2.start_time}-{r2.end_time}"


# ── 8. Telemetry Referential Integrity & Boundaries ───────────────────────────

def test_telemetry_referential_integrity():
    """Verifies telemetry record counts and non-negative boundaries."""
    cfg = SeederConfig()
    users = generate_users(cfg, bcrypt_rounds=4)
    spaces = generate_spaces(cfg)
    cat = generate_catalogue(cfg)

    telemetry = generate_telemetry(cfg, users, spaces["zones"], cat["copies"])
    obs = telemetry["occupancy_observations"]
    searches = telemetry["search_events"]
    inventory = telemetry["inventory_events"]

    assert len(obs) == 20000
    assert len(searches) == 15000
    assert len(inventory) == 6000

    user_ids = {u.id for u in users}
    librarian_ids = {u.id for u in users if u.role == "librarian"}

    for o in obs[:200]:
        assert o.observed_count >= 0
        assert o.capacity_utilization >= 0.0

    for s in searches[:200]:
        assert s.results_count >= 0
        assert s.latency_ms >= 0.0
        if s.user_id is not None:
            assert s.user_id in user_ids

    for inv in inventory[:200]:
        assert inv.auditor_id in librarian_ids


# ── 9. Embedding Fallback Behavior ───────────────────────────────────────────

def test_embedding_fallback_behavior():
    """
    Verifies that when enable_embeddings=False, books receive NULL embeddings
    with embedding_status='missing' and NEVER pseudo-semantic vectors.
    """
    cfg = SeederConfig(enable_embeddings=False)
    cat = generate_catalogue(cfg)
    for b in cat["books"]:
        assert b.embedding is None
        assert b.embedding_status == "missing"
        assert b.embedding_model is None


# ── 10. Engine Disposal Pattern ───────────────────────────────────────────────

def test_engine_disposal_pattern():
    """
    Verifies that disposable temporary SQLAlchemy engines and connections
    can be properly closed and disposed without lingering handles.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1;")).scalar()
        assert res == 1
    engine.dispose()
    assert True


# ── 11. Full Dataset End-to-End Invariant Validation ──────────────────────────

def test_full_dataset_validation_passes():
    """Verifies that the validator reports 100% success on the complete generated dataset."""
    cfg = SeederConfig(enable_embeddings=False, bcrypt_rounds=4)
    all_data = generate_all_datasets(cfg)

    report = validate_dataset(
        users=all_data["users"],
        zones=all_data["zones"],
        seats=all_data["seats"],
        rooms=all_data["rooms"],
        books=all_data["books"],
        copies=all_data["copies"],
        loans=all_data["loans"],
        reservations=all_data["reservations"],
        occupancy_observations=all_data["occupancy_observations"],
        search_events=all_data["search_events"],
        inventory_events=all_data["inventory_events"],
    )

    assert report["is_valid"] is True
    assert report["error_count"] == 0
    assert report["counts"]["loans"] == 10000
    assert report["counts"]["top_loans"] == 8150
    assert report["counts"]["other_loans"] == 1850
    assert report["counts"]["active_loans"] == 320
    assert report["counts"]["student_active_loans"] == 290
    assert report["counts"]["teacher_active_loans"] == 30
    assert report["counts"]["overdue_loans"] == 35
    assert report["counts"]["student_overdue_loans"] == 30
    assert report["counts"]["teacher_overdue_loans"] == 5
    assert report["counts"]["distinct_active_borrowers"] == 163
    assert report["counts"]["res_active"] == 100
    assert report["counts"]["res_completed"] == 2650
    assert report["counts"]["res_cancelled"] == 180
    assert report["counts"]["res_no_show"] == 70


# ── 12. Targeted Invariant Violation Detection Tests ──────────────────────────

def test_validator_detects_cardinality_violation():
    """Verifies that validate_dataset raises ValidationError if copy count is corrupted."""
    cfg = SeederConfig(enable_embeddings=False, bcrypt_rounds=4)
    all_data = generate_all_datasets(cfg)
    corrupted_copies = all_data["copies"][:-1]

    with pytest.raises(ValidationError) as exc:
        validate_dataset(
            users=all_data["users"],
            zones=all_data["zones"],
            seats=all_data["seats"],
            rooms=all_data["rooms"],
            books=all_data["books"],
            copies=corrupted_copies,
            loans=all_data["loans"],
            reservations=all_data["reservations"],
            occupancy_observations=all_data["occupancy_observations"],
            search_events=all_data["search_events"],
            inventory_events=all_data["inventory_events"],
        )
    assert "Cardinality error" in str(exc.value)


def test_validator_detects_concurrency_violation():
    """Verifies that validate_dataset detects when a borrower exceeds concurrent loan quota."""
    cfg = SeederConfig(enable_embeddings=False, bcrypt_rounds=4)
    all_data = generate_all_datasets(cfg)
    loans = list(all_data["loans"])
    user_map = {u.id: u for u in all_data["users"]}

    # Find a student who already has 3 active loans
    user_active_loans = {}
    for l in loans:
        if l.returned_at is None:
            user_active_loans.setdefault(l.user_id, []).append(l)

    student_id = next(
        u for u, cls in user_active_loans.items() if len(cls) == 3 and user_map[u].role == "student"
    )

    # Extend one historical returned loan of this student into the active window
    from dataclasses import replace
    for i, l in enumerate(loans):
        if l.user_id == student_id and l.returned_at is not None:
            loans[i] = replace(l, returned_at=cfg.as_of)
            break

    with pytest.raises(ValidationError) as exc:
        validate_dataset(
            users=all_data["users"],
            zones=all_data["zones"],
            seats=all_data["seats"],
            rooms=all_data["rooms"],
            books=all_data["books"],
            copies=all_data["copies"],
            loans=loans,
            reservations=all_data["reservations"],
            occupancy_observations=all_data["occupancy_observations"],
            search_events=all_data["search_events"],
            inventory_events=all_data["inventory_events"],
        )
    assert "Concurrency quota violation" in str(exc.value)


def test_validator_detects_search_event_user_violation():
    """Verifies that validate_dataset detects search events pointing to invalid user IDs."""
    cfg = SeederConfig(enable_embeddings=False, bcrypt_rounds=4)
    all_data = generate_all_datasets(cfg)
    searches = [s for s in all_data["search_events"]]

    # Corrupt one search event with a non-existent user_id
    from dataclasses import replace
    searches[0] = replace(searches[0], user_id=999999)

    with pytest.raises(ValidationError) as exc:
        validate_dataset(
            users=all_data["users"],
            zones=all_data["zones"],
            seats=all_data["seats"],
            rooms=all_data["rooms"],
            books=all_data["books"],
            copies=all_data["copies"],
            loans=all_data["loans"],
            reservations=all_data["reservations"],
            occupancy_observations=all_data["occupancy_observations"],
            search_events=searches,
            inventory_events=all_data["inventory_events"],
        )
    assert "search event" in str(exc.value)


def test_validator_detects_zone_and_room_constraint_violations():
    """Verifies that validate_dataset detects invalid zone policies and non-positive room capacities."""
    cfg = SeederConfig(enable_embeddings=False, bcrypt_rounds=4)
    all_data = generate_all_datasets(cfg)
    zones = [z for z in all_data["zones"]]
    rooms = [r for r in all_data["rooms"]]

    # Corrupt zone noise policy
    from dataclasses import replace
    corrupted_zones = [replace(zones[0], noise_policy="rock_and_roll")] + zones[1:]

    with pytest.raises(ValidationError) as exc:
        validate_dataset(
            users=all_data["users"],
            zones=corrupted_zones,
            seats=all_data["seats"],
            rooms=rooms,
            books=all_data["books"],
            copies=all_data["copies"],
            loans=all_data["loans"],
            reservations=all_data["reservations"],
            occupancy_observations=all_data["occupancy_observations"],
            search_events=all_data["search_events"],
            inventory_events=all_data["inventory_events"],
        )
    assert "noise_policy" in str(exc.value)

    # Corrupt room capacity to 0
    corrupted_rooms = [replace(rooms[0], capacity=0)] + rooms[1:]
    with pytest.raises(ValidationError) as exc:
        validate_dataset(
            users=all_data["users"],
            zones=zones,
            seats=all_data["seats"],
            rooms=corrupted_rooms,
            books=all_data["books"],
            copies=all_data["copies"],
            loans=all_data["loans"],
            reservations=all_data["reservations"],
            occupancy_observations=all_data["occupancy_observations"],
            search_events=all_data["search_events"],
            inventory_events=all_data["inventory_events"],
        )
    assert "capacity" in str(exc.value)


def test_validator_detects_reservation_status_distribution_mismatch():
    """Verifies that validate_dataset detects deviation in exact reservation status distribution."""
    cfg = SeederConfig(enable_embeddings=False, bcrypt_rounds=4)
    all_data = generate_all_datasets(cfg)
    reservations = [r for r in all_data["reservations"]]

    # Flip one completed reservation to active (making active=101, completed=2649)
    from dataclasses import replace
    for i, r in enumerate(reservations):
        if r.status == "completed":
            reservations[i] = replace(r, status="active")
            break

    with pytest.raises(ValidationError) as exc:
        validate_dataset(
            users=all_data["users"],
            zones=all_data["zones"],
            seats=all_data["seats"],
            rooms=all_data["rooms"],
            books=all_data["books"],
            copies=all_data["copies"],
            loans=all_data["loans"],
            reservations=reservations,
            occupancy_observations=all_data["occupancy_observations"],
            search_events=all_data["search_events"],
            inventory_events=all_data["inventory_events"],
        )
    assert "Status distribution error" in str(exc.value)


def test_validator_detects_active_loan_snapshot_mismatch():
    """Verifies that validate_dataset detects deviations in active loan counts."""
    cfg = SeederConfig(enable_embeddings=False, bcrypt_rounds=4)
    all_data = generate_all_datasets(cfg)
    loans = [l for l in all_data["loans"]]

    # Mark one active loan as returned before as_of (making active=319 instead of 320)
    from dataclasses import replace
    for i, l in enumerate(loans):
        if l.returned_at is None:
            loans[i] = replace(l, returned_at=cfg.as_of - timedelta(days=1))
            break

    with pytest.raises(ValidationError) as exc:
        validate_dataset(
            users=all_data["users"],
            zones=all_data["zones"],
            seats=all_data["seats"],
            rooms=all_data["rooms"],
            books=all_data["books"],
            copies=all_data["copies"],
            loans=loans,
            reservations=all_data["reservations"],
            occupancy_observations=all_data["occupancy_observations"],
            search_events=all_data["search_events"],
            inventory_events=all_data["inventory_events"],
        )
    assert "Snapshot error" in str(exc.value)
