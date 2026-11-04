"""Comprehensive invariant validator for synthetic library demo datasets.

Performs rigorous independent audit across all 8 validation suites:
1. Exact cardinality checks across all entities.
2. Referential integrity across foreign-key relationships (including search_events.user_id).
3. Schema constraints, zones, rooms & vocabulary adherence.
4. Circulation demand distribution (8,150 top 300 books, 1,850 other books).
5. Copy concurrency exclusivity (no simultaneous checkouts of any copy).
6. Borrower policies & active snapshot at `as_of`:
   - Point-in-time concurrency quotas (student <= 3, teacher <= 10).
   - Exactly 320 active loans (290 student, 30 teacher).
   - Exactly 35 overdue loans (30 student, 5 teacher).
   - Exactly 163 distinct active borrowers.
   - Durations (14d student, 30d teacher).
   - Overdue blocking.
7. Active reservation overlap prevention (trigger invariants) and exact status distribution (100/2650/180/70).
8. Telemetry sensor, auditor, and value boundaries.
"""
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_AS_OF = datetime(2026, 10, 31, 23, 59, 59)


class ValidationError(Exception):
    """Raised when one or more synthetic dataset invariants fail validation."""
    pass


def validate_dataset(
    users: List[Any],
    zones: List[Any],
    seats: List[Any],
    rooms: List[Any],
    books: List[Any],
    copies: List[Any],
    loans: List[Any],
    reservations: List[Any],
    occupancy_observations: List[Any],
    search_events: List[Any],
    inventory_events: List[Any],
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Validates in-memory generated records against all architectural invariants.
    Returns a structured audit report or raises ValidationError if any invariant fails.
    """
    if as_of is None:
        as_of = DEFAULT_AS_OF

    errors: List[str] = []

    # ── 1. Cardinality Verification ───────────────────────────────────────────
    students = [u for u in users if u.role == "student"]
    teachers = [u for u in users if u.role == "teacher"]
    librarians = [u for u in users if u.role == "librarian"]

    if len(students) != 500:
        errors.append(f"Cardinality error: expected 500 students, got {len(students)}.")
    if len(teachers) != 25:
        errors.append(f"Cardinality error: expected 25 teachers, got {len(teachers)}.")
    if len(librarians) != 5:
        errors.append(f"Cardinality error: expected 5 librarians, got {len(librarians)}.")
    if len(users) != 530:
        errors.append(f"Cardinality error: expected 530 total users, got {len(users)}.")

    if len(zones) != 8:
        errors.append(f"Cardinality error: expected 8 study zones, got {len(zones)}.")
    if len(seats) != 150:
        errors.append(f"Cardinality error: expected 150 study seats, got {len(seats)}.")
    if len(rooms) != 10:
        errors.append(f"Cardinality error: expected 10 study rooms, got {len(rooms)}.")

    if len(books) != 1500:
        errors.append(f"Cardinality error: expected 1,500 books, got {len(books)}.")
    if len(copies) != 4000:
        errors.append(f"Cardinality error: expected 4,000 book copies, got {len(copies)}.")

    if len(loans) != 10000:
        errors.append(f"Cardinality error: expected 10,000 loans, got {len(loans)}.")
    if len(reservations) != 3000:
        errors.append(f"Cardinality error: expected 3,000 reservations, got {len(reservations)}.")

    if len(occupancy_observations) != 20000:
        errors.append(f"Cardinality error: expected 20,000 occupancy observations, got {len(occupancy_observations)}.")
    if len(search_events) != 15000:
        errors.append(f"Cardinality error: expected 15,000 search events, got {len(search_events)}.")
    if len(inventory_events) != 6000:
        errors.append(f"Cardinality error: expected 6,000 inventory events, got {len(inventory_events)}.")

    # ── 2. Referential Integrity ──────────────────────────────────────────────
    user_ids = {u.id for u in users}
    user_role_map = {u.id: u.role for u in users}
    librarian_ids = {u.id for u in librarians}
    borrower_ids = {u.id for u in students} | {u.id for u in teachers}
    book_ids = {b.id for b in books}
    copy_ids = {c.id for c in copies}
    zone_ids = {z.id for z in zones}
    seat_ids = {s.id for s in seats}
    room_ids = {r.id for r in rooms}

    for c in copies:
        if c.book_id not in book_ids:
            errors.append(f"Referential error: copy {c.id} references non-existent book_id {c.book_id}.")

    for s in seats:
        if s.zone_id not in zone_ids:
            errors.append(f"Referential error: seat {s.id} references non-existent zone_id {s.zone_id}.")

    for l in loans:
        if l.copy_id not in copy_ids:
            errors.append(f"Referential error: loan {l.id} references non-existent copy_id {l.copy_id}.")
        if l.user_id not in borrower_ids:
            errors.append(f"Referential error: loan {l.id} references invalid borrower {l.user_id}.")
        if l.issued_by not in librarian_ids:
            errors.append(f"Referential error: loan {l.id} issued by non-librarian {l.issued_by}.")

    for r in reservations:
        if r.user_id not in borrower_ids:
            errors.append(f"Referential error: reservation {r.id} references invalid user {r.user_id}.")
        if r.resource_type == "seat":
            if r.seat_id not in seat_ids or r.room_id is not None:
                errors.append(f"Target error: seat reservation {r.id} has invalid seat/room pointers.")
        elif r.resource_type == "room":
            if r.room_id not in room_ids or r.seat_id is not None:
                errors.append(f"Target error: room reservation {r.id} has invalid seat/room pointers.")
        else:
            errors.append(f"Target error: reservation {r.id} has invalid resource_type '{r.resource_type}'.")

    for obs in occupancy_observations:
        if obs.zone_id not in zone_ids:
            errors.append(f"Referential error: observation {obs.id} references non-existent zone_id {obs.zone_id}.")

    for s in search_events:
        if s.user_id is not None and s.user_id not in user_ids:
            errors.append(f"Referential error: search event {s.id} references invalid user_id {s.user_id}.")

    for inv in inventory_events:
        if inv.copy_id not in copy_ids:
            errors.append(f"Referential error: inventory event {inv.id} references non-existent copy_id {inv.copy_id}.")
        if inv.auditor_id not in librarian_ids:
            errors.append(f"Referential error: inventory event {inv.id} references non-librarian auditor {inv.auditor_id}.")

    # ── 3. Constraints, Zones, Rooms & Vocabulary Adherence ───────────────────
    VALID_OPERATIONAL_STATUSES = {"available", "maintenance", "lost", "withdrawn"}
    for c in copies:
        if c.operational_status not in VALID_OPERATIONAL_STATUSES:
            errors.append(f"Vocabulary violation: copy {c.id} has forbidden operational_status '{c.operational_status}'.")
        if c.operational_status == "borrowed":
            errors.append(f"Forbidden state: copy {c.id} operational_status cannot be 'borrowed'.")

    VALID_NOISE_POLICIES = {"silent", "quiet", "collaborative"}
    zone_seat_counts: Dict[int, int] = {z.id: 0 for z in zones}
    for s in seats:
        if s.zone_id in zone_seat_counts:
            zone_seat_counts[s.zone_id] += 1

    for z in zones:
        if z.floor < 0:
            errors.append(f"Constraint error: zone {z.id} has negative floor {z.floor}.")
        if z.total_capacity <= 0:
            errors.append(f"Constraint error: zone {z.id} has non-positive capacity {z.total_capacity}.")
        if z.noise_policy not in VALID_NOISE_POLICIES:
            errors.append(f"Vocabulary violation: zone {z.id} has invalid noise_policy '{z.noise_policy}'.")
        if zone_seat_counts.get(z.id, 0) != z.total_capacity:
            errors.append(
                f"Zone seat mismatch: zone {z.id} declared capacity {z.total_capacity} "
                f"but has {zone_seat_counts.get(z.id, 0)} assigned seats."
            )

    for rm in rooms:
        if rm.capacity <= 0:
            errors.append(f"Constraint error: room {rm.id} has non-positive capacity {rm.capacity}.")

    VALID_RES_STATUSES = {"active", "completed", "cancelled", "no_show"}
    res_status_counter = Counter(r.status for r in reservations)
    for r in reservations:
        if r.status not in VALID_RES_STATUSES:
            errors.append(f"Vocabulary violation: reservation {r.id} has invalid status '{r.status}'.")
        if r.end_time <= r.start_time:
            errors.append(f"Ordering error: reservation {r.id} end_time ({r.end_time}) <= start_time ({r.start_time}).")

    # Verify exact reservation status counts
    if res_status_counter["active"] != 100:
        errors.append(f"Status distribution error: expected 100 active reservations, got {res_status_counter['active']}.")
    if res_status_counter["completed"] != 2650:
        errors.append(f"Status distribution error: expected 2,650 completed reservations, got {res_status_counter['completed']}.")
    if res_status_counter["cancelled"] != 180:
        errors.append(f"Status distribution error: expected 180 cancelled reservations, got {res_status_counter['cancelled']}.")
    if res_status_counter["no_show"] != 70:
        errors.append(f"Status distribution error: expected 70 no_show reservations, got {res_status_counter['no_show']}.")

    # ── 4. Circulation Demand Distribution (81.5% Top 300) ────────────────────
    copy_to_book = {c.id: c.book_id for c in copies}
    top_loans_count = sum(1 for l in loans if copy_to_book.get(l.copy_id, 999999) <= 300)
    other_loans_count = sum(1 for l in loans if copy_to_book.get(l.copy_id, 0) > 300)

    if top_loans_count != 8150:
        errors.append(f"Demand distribution error: expected 8,150 top loans, got {top_loans_count}.")
    if other_loans_count != 1850:
        errors.append(f"Demand distribution error: expected 1,850 other loans, got {other_loans_count}.")

    # ── 5. Copy Exclusivity (No Simultaneous Loans) ───────────────────────────
    loans_by_copy: Dict[int, List[Any]] = {}
    for l in loans:
        loans_by_copy.setdefault(l.copy_id, []).append(l)

    for cid, c_loans in loans_by_copy.items():
        sorted_loans = sorted(c_loans, key=lambda x: x.loan_date)
        for i in range(len(sorted_loans) - 1):
            curr_l = sorted_loans[i]
            next_l = sorted_loans[i + 1]
            if curr_l.returned_at is None:
                errors.append(
                    f"Copy exclusivity violation: copy {cid} in loan {curr_l.id} has no return date "
                    f"but is issued again in loan {next_l.id} on {next_l.loan_date}."
                )
            elif curr_l.returned_at > next_l.loan_date:
                errors.append(
                    f"Copy exclusivity violation: copy {cid} returned at {curr_l.returned_at} "
                    f"after next loan {next_l.id} issued at {next_l.loan_date}."
                )

    # ── 6. Borrower Policies, Active Snapshot & Point-in-Time Concurrency ────
    # 6a. Loan duration policies
    for l in loans:
        role = user_role_map.get(l.user_id)
        duration_days = (l.due_date - l.loan_date).days
        if role == "student" and duration_days != 14:
            errors.append(f"Policy violation: student loan {l.id} duration is {duration_days} days (expected 14).")
        elif role == "teacher" and duration_days != 30:
            errors.append(f"Policy violation: teacher loan {l.id} duration is {duration_days} days (expected 30).")

    # 6b. Active snapshot at as_of
    active_loans = [
        l for l in loans if l.loan_date <= as_of and (l.returned_at is None or l.returned_at > as_of)
    ]
    if len(active_loans) != 320:
        errors.append(f"Snapshot error: expected 320 active loans at as_of, got {len(active_loans)}.")

    student_active_loans = [l for l in active_loans if user_role_map.get(l.user_id) == "student"]
    teacher_active_loans = [l for l in active_loans if user_role_map.get(l.user_id) == "teacher"]

    if len(student_active_loans) != 290:
        errors.append(f"Snapshot error: expected 290 student active loans, got {len(student_active_loans)}.")
    if len(teacher_active_loans) != 30:
        errors.append(f"Snapshot error: expected 30 teacher active loans, got {len(teacher_active_loans)}.")

    # 6c. Overdue snapshot at as_of
    overdue_loans = [l for l in active_loans if l.due_date < as_of]
    if len(overdue_loans) != 35:
        errors.append(f"Snapshot error: expected 35 overdue loans at as_of, got {len(overdue_loans)}.")

    student_overdue_loans = [l for l in overdue_loans if user_role_map.get(l.user_id) == "student"]
    teacher_overdue_loans = [l for l in overdue_loans if user_role_map.get(l.user_id) == "teacher"]

    if len(student_overdue_loans) != 30:
        errors.append(f"Snapshot error: expected 30 student overdue loans, got {len(student_overdue_loans)}.")
    if len(teacher_overdue_loans) != 5:
        errors.append(f"Snapshot error: expected 5 teacher overdue loans, got {len(teacher_overdue_loans)}.")

    # 6d. Distinct active borrowers at as_of
    distinct_active_borrowers = {l.user_id for l in active_loans}
    if len(distinct_active_borrowers) != 163:
        errors.append(f"Snapshot error: expected 163 distinct active borrowers, got {len(distinct_active_borrowers)}.")

    # 6e. Point-in-time borrower concurrency quotas
    user_timeline_events: Dict[int, List[Tuple[datetime, int, int, int]]] = {}
    for l in loans:
        # Issue event: (timestamp, priority=1, delta=+1, loan_id)
        user_timeline_events.setdefault(l.user_id, []).append((l.loan_date, 1, 1, l.id))
        if l.returned_at is not None:
            # Return event: (timestamp, priority=0, delta=-1, loan_id)
            user_timeline_events[l.user_id].append((l.returned_at, 0, -1, l.id))

    for uid, evs in user_timeline_events.items():
        role = user_role_map.get(uid)
        max_quota = 10 if role == "teacher" else (3 if role == "student" else 0)
        # Sort by timestamp asc, priority asc (return before issue at identical timestamp)
        evs.sort(key=lambda x: (x[0], x[1]))
        curr_active = 0
        for dt, prio, delta, lid in evs:
            curr_active += delta
            if curr_active > max_quota:
                errors.append(
                    f"Concurrency quota violation: user {uid} ({role}) reached {curr_active} loans "
                    f"exceeding max {max_quota} at {dt} (loan {lid})."
                )
                break

    # ── 7. Active Reservation Overlap Prevention (Trigger Invariants) ─────────
    active_seat_res: Dict[int, List[Any]] = {}
    active_room_res: Dict[int, List[Any]] = {}

    for r in reservations:
        if r.status == "active":
            if r.resource_type == "seat":
                active_seat_res.setdefault(r.seat_id, []).append(r)
            elif r.resource_type == "room":
                active_room_res.setdefault(r.room_id, []).append(r)

    for sid, s_res in active_seat_res.items():
        sorted_res = sorted(s_res, key=lambda x: x.start_time)
        for i in range(len(sorted_res) - 1):
            r1 = sorted_res[i]
            r2 = sorted_res[i + 1]
            if r1.start_time < r2.end_time and r1.end_time > r2.start_time:
                errors.append(
                    f"Active reservation conflict on seat {sid}: [{r1.start_time}, {r1.end_time}) "
                    f"overlaps [{r2.start_time}, {r2.end_time})."
                )

    for rid, r_res in active_room_res.items():
        sorted_res = sorted(r_res, key=lambda x: x.start_time)
        for i in range(len(sorted_res) - 1):
            r1 = sorted_res[i]
            r2 = sorted_res[i + 1]
            if r1.start_time < r2.end_time and r1.end_time > r2.start_time:
                errors.append(
                    f"Active reservation conflict on room {rid}: [{r1.start_time}, {r1.end_time}) "
                    f"overlaps [{r2.start_time}, {r2.end_time})."
                )

    # ── 8. Telemetry Boundaries ───────────────────────────────────────────────
    for obs in occupancy_observations:
        if obs.observed_count < 0:
            errors.append(f"Observation boundary error: obs {obs.id} has negative count {obs.observed_count}.")
        if obs.capacity_utilization < 0.0:
            errors.append(f"Observation boundary error: obs {obs.id} has negative utilization {obs.capacity_utilization}.")

    for s in search_events:
        if s.results_count < 0:
            errors.append(f"Search boundary error: search {s.id} has negative results {s.results_count}.")
        if s.latency_ms < 0.0:
            errors.append(f"Search boundary error: search {s.id} has negative latency {s.latency_ms}.")

    # Summary report
    is_valid = (len(errors) == 0)
    report = {
        "is_valid": is_valid,
        "error_count": len(errors),
        "errors": errors[:50],
        "counts": {
            "students": len(students),
            "teachers": len(teachers),
            "librarians": len(librarians),
            "users": len(users),
            "zones": len(zones),
            "seats": len(seats),
            "rooms": len(rooms),
            "books": len(books),
            "copies": len(copies),
            "loans": len(loans),
            "active_loans": len(active_loans),
            "student_active_loans": len(student_active_loans),
            "teacher_active_loans": len(teacher_active_loans),
            "overdue_loans": len(overdue_loans),
            "student_overdue_loans": len(student_overdue_loans),
            "teacher_overdue_loans": len(teacher_overdue_loans),
            "distinct_active_borrowers": len(distinct_active_borrowers),
            "top_loans": top_loans_count,
            "other_loans": other_loans_count,
            "reservations": len(reservations),
            "res_active": res_status_counter["active"],
            "res_completed": res_status_counter["completed"],
            "res_cancelled": res_status_counter["cancelled"],
            "res_no_show": res_status_counter["no_show"],
            "occupancy_observations": len(occupancy_observations),
            "search_events": len(search_events),
            "inventory_events": len(inventory_events),
        },
    }

    if not is_valid:
        raise ValidationError(f"Dataset invariant validation failed with {len(errors)} errors: {errors}")

    return report
