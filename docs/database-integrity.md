# Database Baseline Integrity and Fingerprint Reference

**Document Version:** 1.0.0  
**Status:** Approved & Frozen Baseline  
**Active Branch:** `feature/aryan-ai-library-system`  
**Last Verified:** 2026-11-01  

---

## 1. Authoritative Database Inventory & Binary Fingerprints

This document establishes the official cryptographic baselines and logical fingerprints for all database files in the AI Library Management System repository.

| Database Identifier | Relative Path | Role in System | Authoritative SHA-256 Hash | File Size | Alembic Revision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Protected Development DB** | `backend/library.db` | Standard development & baseline testing | `3bd0578347ba99313fd3640669d80f66d6858ecb484a9741b206550ab906fab8` | 323,584 bytes | `0f610073e5f1` |
| **Protected Root Baseline** | `library.db` | Historical clean-schema baseline | `fd764e0b0b5eda1ab0abe932055ee8b2d0e843001571f169760f9d32850d7931` | 98,304 bytes | `0f610073e5f1` |
| **Published Demo Database (Stage 7)** | `backend/library_demo.db` | Synthetic demo dataset with 1,500 dense embeddings | `20b2d18c582a5c205e4cafadd630b2a15cde03cac6ae9d6b775ef33c45ffaaea` | 16,781,312 bytes | `c3d4e5f6a7b8` |
| **Pre-Stage 7 Demo Backup** | `backend/library_demo.db.pre_stage7_backup` | Immutable recovery point prior to embedding population | `df59eba1c765457e5129b5be08917bc4049d7ff250ea4aa080010ad9655c3bd3` | 14,213,120 bytes | `c3d4e5f6a7b8` |

---

## 2. Protected Development Database (`backend/library.db`)

### Forensic Binary Hash Reconciliation Note
The binary SHA-256 of `backend/library.db` previously recorded prior to Stage 6 was `61a9a174346c6551d683586584df32c74b46eb76c7e27fbcb2f3579264b8a403`.

During initial Stage 6 application smoke testing, an automated test process executed before `DEMO_MODE=true` was registered in the runtime environment. FastAPI's lifespan event executed `init_db()`, which applied migrations `b2c3d4e5f6a7` and `c3d4e5f6a7b8` to the database. The database was immediately remediated by running `alembic downgrade 0f610073e5f1` followed by a SQLite `VACUUM`.

While all seven Phase 1 tables and four triggers were cleanly dropped—preserving 100% of the original logical schema, records, indexes, foreign keys, and Alembic version—SQLite's internal B-tree page reorganization and VACUUM operation altered the physical binary byte layout to `3bd0578347ba99313fd3640669d80f66d6858ecb484a9741b206550ab906fab8`.

Following Stage 6.1 forensic verification, this fingerprint is formally accepted and frozen as the authoritative development baseline.

### Logical Fingerprint (`backend/library.db`)
- **Alembic Version:** `0f610073e5f1` (1 row)
- **Table Count:** 5 (`alembic_version`, `book_copies`, `books`, `loans`, `users`)
- **Row Counts:**
  - `users`: 4 accounts (2 students, 2 librarians)
  - `books`: 15 monographs
  - `book_copies`: 31 physical items
  - `loans`: 2 records (1 active, 1 returned)
  - `alembic_version`: 1 row
- **Indexes:** 15 total (including partial index `uix_one_active_loan_per_copy ON loans (copy_id) WHERE returned_at IS NULL`)
- **Triggers:** 0
- **Integrity Status:** `PRAGMA quick_check;` = `ok`, `PRAGMA foreign_key_check;` = 0 violations.

---

## 3. Protected Root Baseline Database (`library.db`)

### Logical Fingerprint (`library.db`)
- **Alembic Version:** `0f610073e5f1` (1 row)
- **Table Count:** 5 (`alembic_version`, `book_copies`, `books`, `loans`, `users`)
- **Row Counts:**
  - `users`: 0
  - `books`: 0
  - `book_copies`: 0
  - `loans`: 0
  - `alembic_version`: 1
- **Indexes:** 15 total
- **Triggers:** 0
- **Integrity Status:** `PRAGMA quick_check;` = `ok`, `PRAGMA foreign_key_check;` = 0 violations.

---

## 4. Published Synthetic Demo Database (`backend/library_demo.db`)

### Logical Fingerprint (`backend/library_demo.db`)
- **Alembic Version:** `c3d4e5f6a7b8` (Head revision)
- **Table Count:** 12 (`alembic_version`, `book_copies`, `books`, `inventory_events`, `loans`, `occupancy_observations`, `reservations`, `search_events`, `study_rooms`, `study_seats`, `study_zones`, `users`)
- **Row Counts (60,199 total rows):**
  - `users`: 530 rows (500 students, 25 teachers, 5 librarians)
  - `study_zones`: 8 rows
  - `study_seats`: 150 rows
  - `study_rooms`: 10 rows
  - `books`: 1,500 rows (all monographs generated deterministically)
  - `book_copies`: 4,000 rows
  - `loans`: 10,000 rows (320 active, 35 overdue relative to `as_of = 2026-03-31`)
  - `reservations`: 3,000 rows (180 active seat/room reservations)
  - `occupancy_observations`: 20,000 observations
  - `search_events`: 15,000 telemetry records
  - `inventory_events`: 6,000 physical audit logs
  - `alembic_version`: 1 row
- **Triggers (4 total):**
  - `trg_prevent_seat_reservation_insert`
  - `trg_prevent_seat_reservation_update`
  - `trg_prevent_room_reservation_insert`
  - `trg_prevent_room_reservation_update`
- **Integrity Status:** `PRAGMA quick_check;` = `ok`, `PRAGMA foreign_key_check;` = 0 violations.
- **Dense Vector Embeddings (Stage 7):**
  - **Embedded Books:** 1,500 / 1,500 (100% complete, 0 NULLs, 0 missing)
  - **Embedding Staleness:** 0 stale records (`embedding_updated_at >= updated_at` for all 1,500 books)
  - **Model Architecture:** `sentence-transformers/all-MiniLM-L6-v2` (Snapshot: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`)
  - **Vector Dimensions:** 384 dimensions (`float32` little-endian raw bytes, 1,536 bytes per vector)
  - **Normalization:** L2 unit norm (`||v||_2 ≈ 1.0`, min=0.99999988, max=1.00000012, avg=1.00000000)
  - **Provenance File:** `backend/app/seed_data/embedding_provenance.json`

---

## 5. Startup Protection Architecture

To guarantee that protected databases cannot be inadvertently modified or migrated:

1. **`is_protected_database(url)` Invariant:**  
   Every database URL passed to `init_db()` or `run_migrations()` is resolved against filesystem canonical paths. Any URL or relative alias resolving to `backend/library.db` or root `library.db` is intercepted immediately.
2. **`ProtectedDatabaseMigrationError` Enforcement:**  
   Automatic schema migration attempts targeting protected databases are rejected with `ProtectedDatabaseMigrationError`.
3. **Explicit Opt-in Requirement:**  
   Intentional migration of a protected database requires setting the environment variable `ALLOW_PROTECTED_DB_MIGRATION=true` or passing `allow_protected_migration=True`.
4. **Demo Mode Read-Only Guarantee:**  
   When `DEMO_MODE=true`, `validate_demo_database()` opens the demo database with URI parameter `mode=ro`, runs non-destructive checks, and never executes DDL migrations.

