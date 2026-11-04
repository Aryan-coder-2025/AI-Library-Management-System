# Study Space Transactional Architecture & Hardening Specification (Stage 10.2.2)

## 1. Overview & Objective

This document defines the hardened transactional architecture for the Study Space Reservation subsystem (`SPAC-01` through `SPAC-05`), addressing edge cases, exception sanitization, and multithreaded concurrency guarantees established in Stage 10.2.2.

---

## 2. Invariant Specifications

### 2.1 Strict Booking-Time Invariant (Phase A)
- **Mathematical Invariant:** `start_time >= now_utc`
- **Tolerance Policy:** Exactly zero tolerance for past starts. Any booking start time strictly earlier than `now_utc` ($start\_time < now\_utc$, even by 1 microsecond) is rejected with HTTP 400 Bad Request (`detail: "Reservation start time cannot be in the past."`).
- **Exact Equality:** A start time precisely equal to `now_utc` ($start\_time == now\_utc$) is accepted if all other operational and resource constraints pass.
- **Clock Abstraction:** `validate_reservation_times` accepts an optional `now_utc: Optional[datetime]` clock injection parameter. In production execution, `datetime.utcnow()` captures a single monotonic instant per validation pass, preventing clock skew between interval checks.
- **Timezone Normalization:** Incoming client datetimes with timezone offsets (e.g. ISO 8601 strings with `+05:30` or `Z`) are normalized to naive UTC via `normalize_utc_datetime()` before any arithmetic or database persistence.
- **Operating Hours:** Institutional operating hours (`08:00` to `22:00` in `Asia/Kolkata`) and calendar-day bounds are evaluated by projecting normalized UTC values into the institutional timezone (`get_library_timezone("Asia/Kolkata")`).

### 2.2 Database Exception Classification Architecture (Phase B)
Database exceptions during study space operations are classified based on their underlying driver cause, inspecting SQLAlchemy error metadata and SQLite driver properties (`sqlite_errorcode`, `sqlite_errorname`):

| Database Error Scenario | Driver / Cause Metadata | HTTP Status | Response Payload | Information Leakage Protection |
| :--- | :--- | :---: | :--- | :--- |
| **Known Resource Collision** | Trigger `trg_prevent_seat_overlap`, `trg_prevent_room_overlap`, or overlap check | `HTTP 409 Conflict` | Generic conflict description (`"Reservation conflict: resource or user already has an active reservation during this time interval."`) | Strips all SQL statements, trigger names, and internal column IDs. |
| **Known User Self-Overlap** | Trigger `trg_prevent_user_reservation_overlap` or service-level active check | `HTTP 409 Conflict` | Generic conflict description | No schema or trigger details leaked. |
| **Reservation Uniqueness** | `UNIQUE constraint failed: reservations.*` | `HTTP 409 Conflict` | Generic conflict description | Strips table names and index names. |
| **Lock Contention / Busy Timeout** | `SQLITE_BUSY` (code 5), `SQLITE_LOCKED` (code 6), or `"database is locked"` | `HTTP 503 Service Unavailable` | `"The reservation service is currently busy. Please retry your request shortly."`<br>Header: `Retry-After: 1` | Never returned as HTTP 400. Driver strings concealed. |
| **Unexpected Integrity Violation** | Foreign key violation, check violation on unrelated domain | `HTTP 500 Internal Server Error` | `"An internal database integrity error occurred while processing the reservation."` | Logged internally with `exc_info=True`. Client receives zero technical details. |
| **Unexpected Operational Failure** | Disk I/O error, corrupt page, schema mismatch | `HTTP 500 Internal Server Error` | `"An internal database operational error occurred while processing the reservation."` | Logged internally with `exc_info=True`. Client receives zero technical details. |

### 2.3 Transaction Ownership & Rollback Hygiene
- **Authoritative Ownership:** The FastAPI dependency `get_write_db()` in [`backend/app/database.py`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/app/database.py) owns the commit/rollback lifecycle for API endpoints.
- **No Manual Commits in Services:** Service functions call `db.flush()` to trigger SQL execution and database trigger evaluation within the active write transaction, but never call `db.commit()`.
- **Automatic Rollback:** If an exception escapes from `create_reservation_service` or `cancel_reservation_service`, `get_write_db()` guarantees `db.rollback()` and session cleanup.
- **Savepoint Support:** When `atomic_write(session)` is nested within an existing transaction, it utilizes a savepoint (`begin_nested()`) to guarantee atomicity without prematurely committing outer transactions.

---

## 3. Concurrency Guarantees & Engine Mechanics

### 3.1 SQLite `BEGIN IMMEDIATE` Serialization
SQLite by default operates in `DEFERRED` transaction mode, which defers write locking until the first DML operation (`INSERT`/`UPDATE`). Under concurrent read-check-write patterns, this creates Time-Of-Check-To-Time-Of-Use (TOCTOU) race conditions where two connections read a resource as available, and both attempt to write, leading to deadlocks or collisions.

To eliminate this:
1. `get_write_db()` and `atomic_write()` issue `BEGIN IMMEDIATE` upfront via SQLAlchemy execution options (`{"sqlite_immediate": True}`).
2. `BEGIN IMMEDIATE` acquires a `RESERVED` lock immediately, preventing any other connection from beginning a write transaction until the current transaction commits or rolls back.
3. Readers operating in Write-Ahead Logging (WAL) mode continue concurrently without blocking or being blocked by the immediate write transaction.
4. If a second writer attempts `BEGIN IMMEDIATE` while another write transaction is active, SQLite waits for the configured `busy_timeout` (5,000 ms). If the lock is not released within the timeout, SQLite returns `SQLITE_BUSY` / `SQLITE_LOCKED`, which the application maps cleanly to `HTTP 503 Service Unavailable` with `Retry-After: 1`.

### 3.2 Realistic Concurrency Scope
> [!NOTE]
> The reservation service does **not** provide unlimited horizontal scale or zero-contention throughput. As a single-file SQLite database in WAL mode, concurrent writes are strictly serialized. Maximum write concurrency is bounded by SQLite transaction duration ($\approx 1\text{–}5\text{ ms}$ per reservation), translating to approximately 200–1,000 serialized booking writes per second under optimal I/O conditions.

---

## 4. Concurrency Verification Test Suite

The test suite in [`backend/tests/test_study_space_service.py`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/tests/test_study_space_service.py) contains genuine multithreaded concurrency tests running against isolated temporary file-backed SQLite databases (`tmp_path`):

1. **Test A — Same-Resource Collision (`test_concurrent_same_resource_collision`):**
   - **Workers:** 5 concurrent threads (`ThreadPoolExecutor`).
   - **Coordination:** `threading.Barrier(5)` synchronizes threads immediately before transaction entry.
   - **Target:** 5 simultaneous booking attempts targeting Seat 1 during an identical time interval.
   - **Outcome:** Exactly 1 thread succeeds (HTTP 201); exactly 4 threads fail with HTTP 409 Conflict.
   - **Verification:** Independent database inspection confirms exactly 1 active reservation in the database.

2. **Test B — Student Quota Race (`test_concurrent_student_quota_race`):**
   - **Workers:** 2 concurrent threads (`ThreadPoolExecutor`).
   - **Coordination:** `threading.Barrier(2)` synchronizes threads.
   - **Target:** 2 simultaneous requests from the same student for distinct resources (Seat 1 and Seat 2) during non-overlapping intervals (student quota is 1).
   - **Outcome:** Exactly 1 thread succeeds; exactly 1 thread fails with HTTP 400 Bad Request (`"maximum allowed active reservations for their role (1)"`).
   - **Verification:** Independent database inspection confirms exactly 1 active reservation for that student.

3. **Test C — Teacher Quota Race (`test_concurrent_teacher_quota_race`):**
   - **Workers:** 3 concurrent threads (`ThreadPoolExecutor`).
   - **Coordination:** `threading.Barrier(3)` synchronizes threads.
   - **Target:** 3 simultaneous requests from the same teacher for distinct resources (Seats 1, 2, 3) during non-overlapping intervals (teacher quota is 2).
   - **Outcome:** Exactly 2 threads succeed; exactly 1 thread fails with HTTP 400 Bad Request (`"maximum allowed active reservations for their role (2)"`).
   - **Verification:** Independent database inspection confirms exactly 2 active reservations for that teacher.

4. **Test D — SQLite Contention & Busy Timeout (`test_concurrent_lock_contention_and_busy_timeout`):**
   - **Coordination:** An independent raw connection holds `BEGIN IMMEDIATE` write lock.
   - **Contention:** A second connection with `PRAGMA busy_timeout = 20;` attempts to book a reservation.
   - **Outcome:** Fails deterministically with `HTTP 503 Service Unavailable`, includes `Retry-After: 1` header, and exposes zero internal driver or SQL details.
   - **Recovery:** Upon release of the blocking connection, subsequent booking request succeeds immediately.

---

## 5. QR Check-In, Grace Periods & Lifecycle Sweep Architecture (Stage 10.3)

### 5.1 QR Check-In Token Mechanics & Defense-in-Depth
- **Dedicated Signing Secret:** Signed using a dedicated `SPACES_QR_SECRET_KEY` (distinct from the primary `JWT_SECRET_KEY`), completely isolating QR tokens from patron session authentication tokens.
- **Token Format:** URL-safe base64-encoded JSON payload concatenated with an HMAC-SHA256 signature (`<payload_b64>.<signature_b64>`), keyed by `SPACES_QR_SECRET_KEY`.
- **Payload Contents:**
  - `sub`: `f"res:{reservation.id}"` (explicitly namespaced subject, preventing numeric cast to `User.id`).
  - `type`: `"study_space_qr_checkin"`.
  - `reservation_id`: Target reservation identifier.
  - `user_id`: Target patron identifier.
  - `resource_type`: `"seat"` or `"room"`.
  - `resource_id`: Target seat or room identifier.
  - `exp`: Token expiry timestamp (Unix epoch), set to `max(now_utc + 30m, reservation.start_time + CHECKIN_GRACE_PERIOD_MINUTES)`.
  - `iat`: Token issuance timestamp (Unix epoch).
  - `jti`: Cryptographically secure 12-byte random hex nonce.
- **Cross-Purpose Token Confusion Defense:** Session authentication tokens strictly require `type: "access"`. Passing a QR token as a Bearer authorization token or in `access_token` cookie fails with `HTTP 401 Unauthorized` due to secret key mismatch, missing `type: "access"` claim, and non-numeric `sub: res:<id>`.
- **Tamper Resistance:** Any payload alteration or signature mismatch produces `HTTP 400 Bad Request` (`"Invalid or expired QR check-in token."`).
- **Expiration Guard:** Expired tokens produce `HTTP 400 Bad Request`.

### 5.2 Check-In Windows & Grace Period Policies
- **Window Opening:** Check-in window opens strictly `CHECKIN_WINDOW_BEFORE_MINUTES` (15 minutes) prior to scheduled `start_time`. Check-in attempts prior to `start_time - 15m` are rejected with `HTTP 400 Bad Request`.
- **Patron Grace Period:** Patrons may check in up to `CHECKIN_GRACE_PERIOD_MINUTES` (15 minutes) after scheduled `start_time`. Late patron attempts after `start_time + 15m` are rejected with `HTTP 400 Bad Request`.
- **Staff Override:** Librarians and system administrators may check in reservations throughout the duration of the scheduled interval up until `end_time`.
- **Post-Interval Hard Stop:** Check-in after scheduled `end_time` is rejected for all roles with `HTTP 400 Bad Request`.
- **Atomic State Mutation:** Check-in utilizes conditional SQL updates:
  ```sql
  UPDATE reservations
  SET checked_in_at = :now_utc, actual_attendees = :attendees
  WHERE id = :id AND status = 'active' AND checked_in_at IS NULL
  ```
  Concurrent or replay attempts update 0 rows and return `HTTP 409 Conflict` (`"Reservation is already checked in."`).

### 5.3 Automated Lifecycle Sweeper & Invariant Guarantees
- **No-Show Transition:** Active reservations where `checked_in_at IS NULL` and `now_utc >= start_time + 15m` are marked `no_show`.
- **Completion Transition:** Active reservations where `checked_in_at IS NOT NULL` and `now_utc >= end_time` are marked `completed`.
- **Critical Invariant:** An un-checked-in reservation (`checked_in_at IS NULL`) whose scheduled `end_time` has elapsed must **never** transition to `completed`. It transitions strictly to `no_show`.
- **Idempotency:** The sweeper evaluates state deterministically and performs 0 mutations if no reservations meet transition criteria.
- **Dual Trigger Paths:**
  1. **REST API:** `POST /api/spaces/reservations/sweep` (librarian/admin restricted).
  2. **CLI Utility:** `python -m app.cli_sweep --spaces` (or combined `--all`).

## 6. Occupancy Tracking, Telemetry & Analytics Architecture (Stage 10.4)

### 6.1 Real-Time Live Occupancy Derivation
- **Methodology:** Real-time occupancy is strictly derived from active study space reservations holding verified check-in evidence (`checked_in_at IS NOT NULL` and `status == 'active'` and `start_time <= now < end_time`).
- **Resource Differentiation:**
  - **Study Seats:** Each checked-in seat reservation contributes exactly 1 occupant to its associated study zone.
  - **Study Rooms:** Each checked-in room reservation contributes `actual_attendees` (or `expected_attendees` if `actual_attendees` was not supplied during check-in), clamped to the room's maximum capacity. Rooms are standalone resources and are not aggregated into zone seat counts, eliminating double-counting.
- **Strict Exclusion:** Reservations in states `cancelled`, `completed`, `no_show`, or un-checked-in `active` bookings outside the current time window contribute 0 occupants.
- **Capacity Bounds:** Reported occupancy is strictly clamped to `[0, total_capacity]`, ensuring utilization percentages never exceed 100.0% even in edge cases.
- **Data Provenance:** Clearly tagged as `"reservation_estimate"`. System documentation and UI explicitly disclaim that this represents reservation-derived bookings rather than optical physical sensor presence.

### 6.2 Telemetry Ingestion & Idempotency Guarantees
- **Model Reuse:** Persists observations directly into `occupancy_observations` (`zone_id`, `recorded_at`, `observed_count`, `capacity_utilization`, `source_sensor_id`).
- **Timestamp Normalization:** Timestamps are normalized to naive UTC for consistent SQLite indexing.
- **Idempotency Strategy:** Telemetry ingestion checks for existing observations matching `(zone_id, recorded_at)`:
  - If identical `observed_count` and `source_sensor_id`: returns existing record with status `"idempotent_duplicate"`.
  - If updated headcount: performs in-place update and returns status `"updated"`.
  - If new observation: inserts new row with status `"recorded"`.
- **Validation:** Headcount must be integer >= 0; target zone must exist and be active; utilization is computed safely as `round(observed_count / zone.total_capacity, 4)` with zero-division protection.
- **Role Guard:** `POST /api/spaces/occupancy/telemetry` is strictly restricted to `librarian` and `admin` roles.

### 6.3 Database SQL Aggregation & Analytics
- **Historical Trends:** Aggregations group by `strftime('%Y-%m-%d', recorded_at)` (daily) or `strftime('%Y-%m-%d %H:00', recorded_at)` (hourly), calculating `AVG(observed_count)`, `MAX(observed_count)`, `MIN(observed_count)`, `AVG(capacity_utilization)`, and `COUNT(id)` directly within SQLite to prevent loading 20,000+ rows into application memory.
- **24-Hour Diurnal Peak Profile:** Groups historical observations by `CAST(strftime('%H', recorded_at) AS INTEGER)`, returning average occupancy and utilization across hours 00:00 to 23:00 and flagging the peak usage hour.
- **Zero-Patron Leak Guarantee:** All public and student-accessible analytics endpoints (`/occupancy/current`, `/occupancy/zones`, `/occupancy/resources`, `/occupancy/historical`, `/occupancy/peak-hours`) return aggregated spatial metrics only, exposing zero user IDs, patron names, or individual reservation records.


