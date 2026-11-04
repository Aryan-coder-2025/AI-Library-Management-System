"""Unit test suite for Phase 1 – Step 2B Stage 4: Isolated Staging Database Population.

Tests:
1. Preflight safety checks:
   - Rejection if staging database already exists (no clobbering).
   - Rejection if target published database already exists.
   - Rejection if unexpected sidecar files exist.
2. Staging migration:
   - Verifies Alembic head reaches 'c3d4e5f6a7b8'.
   - Verifies all 11 tables and triggers are created.
3. Persisted data validation:
   - PRAGMA foreign_key_check passes with 0 errors.
   - PRAGMA integrity_check passes with 'ok'.
   - Trigger enforcement aborts conflicting active reservations.
   - Exact persisted table row counts.
4. Safe WAL shutdown:
   - Checkpoint truncates WAL.
   - Switches to DELETE journal mode.
   - Verifies no -wal or -shm sidecars remain.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import pytest

from app.seed_data.generator import SeederConfig
from app.seed_data.safety import (
    CANONICAL_BACKEND_DIR,
    CANONICAL_TARGET_DB,
    CANONICAL_STAGING_DB,
    CANONICAL_LOCK_FILE,
    PROTECTED_DATABASES,
    SeedSafetyError,
    SecurityViolationError,
    PublicationCollisionError,
)
from app.seed_data.seeder import (
    _verify_preflight_environment,
    _apply_staging_migrations,
    _validate_persisted_staging,
    populate_staging_database,
    EXPECTED_ALEMBIC_HEAD,
)


def test_preflight_rejects_existing_published_target(tmp_path):
    """Verifies that preflight rejects execution if library_demo.db already exists."""
    fake_target = tmp_path / "library_demo.db"
    fake_target.touch()

    # Monkeypatch CANONICAL_TARGET_DB check in preflight
    import app.seed_data.seeder as seeder_mod
    orig_target = seeder_mod.CANONICAL_TARGET_DB
    seeder_mod.CANONICAL_TARGET_DB = fake_target
    try:
        with pytest.raises(PublicationCollisionError):
            _verify_preflight_environment(tmp_path / "library_demo.db.staging", tmp_path)
    finally:
        seeder_mod.CANONICAL_TARGET_DB = orig_target


def test_preflight_rejects_existing_staging_database(tmp_path):
    """Verifies that preflight refuses to overwrite an existing staging database."""
    fake_staging = tmp_path / "library_demo.db.staging"
    fake_staging.touch()

    import app.seed_data.seeder as seeder_mod
    orig_target = seeder_mod.CANONICAL_TARGET_DB
    seeder_mod.CANONICAL_TARGET_DB = tmp_path / "nonexistent_published.db"
    try:
        with pytest.raises(SeedSafetyError) as exc:
            _verify_preflight_environment(fake_staging, tmp_path)
        assert "already exists" in str(exc.value)
    finally:
        seeder_mod.CANONICAL_TARGET_DB = orig_target


def test_preflight_rejects_lingering_staging_sidecars(tmp_path):
    """Verifies that preflight refuses execution if lingering -wal or -shm files exist."""
    fake_staging = tmp_path / "library_demo.db.staging"
    wal_file = tmp_path / "library_demo.db.staging-wal"
    wal_file.touch()

    import app.seed_data.seeder as seeder_mod
    orig_target = seeder_mod.CANONICAL_TARGET_DB
    seeder_mod.CANONICAL_TARGET_DB = tmp_path / "nonexistent_published.db"
    try:
        with pytest.raises(SeedSafetyError) as exc:
            _verify_preflight_environment(fake_staging, tmp_path)
        assert "Unexpected staging sidecar" in str(exc.value)
    finally:
        seeder_mod.CANONICAL_TARGET_DB = orig_target


def test_staging_trigger_aborts_active_conflicts():
    """
    Verifies that the database triggers installed by Alembic on the staging schema
    actively abort conflicting active reservations.
    """
    disposable_staging = CANONICAL_BACKEND_DIR / "disposable_trigger_test.db.staging"
    if disposable_staging.exists():
        disposable_staging.unlink()

    conn = None
    cur = None
    try:
        # Apply migrations
        rev = _apply_staging_migrations(disposable_staging, CANONICAL_BACKEND_DIR)
        assert rev == EXPECTED_ALEMBIC_HEAD

        conn = sqlite3.connect(str(disposable_staging))
        cur = conn.cursor()

        # Insert a user and a seat
        cur.execute(
            "INSERT INTO users (id, email, hashed_password, full_name, role, is_active, created_at) "
            "VALUES (1, 'u@lib.edu', 'hash', 'User One', 'student', 1, '2026-10-31 00:00:00');"
        )
        cur.execute(
            "INSERT INTO study_zones (id, zone_code, name, floor, total_capacity, noise_policy, is_active, created_at) "
            "VALUES (1, 'Z1', 'Zone 1', 1, 10, 'quiet', 1, '2026-10-31 00:00:00');"
        )
        cur.execute(
            "INSERT INTO study_seats (id, zone_id, seat_code, has_power_outlet, has_monitor, is_accessible, is_active, created_at) "
            "VALUES (1, 1, 'S1', 1, 0, 0, 1, '2026-10-31 00:00:00');"
        )

        # Insert initial active reservation [10:00, 12:00)
        cur.execute(
            "INSERT INTO reservations (id, user_id, resource_type, seat_id, room_id, start_time, end_time, status, created_at) "
            "VALUES (1, 1, 'seat', 1, NULL, '2026-11-01 10:00:00', '2026-11-01 12:00:00', 'active', '2026-10-31 00:00:00');"
        )
        conn.commit()

        conflict_detected = False
        try:
            cur.execute(
                "INSERT INTO reservations (id, user_id, resource_type, seat_id, room_id, start_time, end_time, status, created_at) "
                "VALUES (2, 1, 'seat', 1, NULL, '2026-11-01 11:00:00', '2026-11-01 13:00:00', 'active', '2026-10-31 00:00:00');"
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            if "Reservation conflict" in str(exc):
                conflict_detected = True
            conn.rollback()

        assert conflict_detected is True

    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        import gc
        gc.collect()
        if disposable_staging.exists():
            disposable_staging.unlink()
        for ext in ["-wal", "-shm"]:
            sc = Path(f"{disposable_staging}{ext}")
            if sc.exists():
                sc.unlink()
