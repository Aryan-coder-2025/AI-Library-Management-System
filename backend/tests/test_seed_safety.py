"""Comprehensive test suite for Phase 1 – Step 2B Stage 2: Safety Infrastructure.

Tests all security boundaries, path validators, kernel locks, staging isolation,
WAL shutdown protocols, and atomic no-overwrite publication primitives.
"""
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest

from app.seed_data.safety import (
    CANONICAL_BACKEND_DIR,
    CANONICAL_TARGET_DB,
    CANONICAL_STAGING_DB,
    CANONICAL_LOCK_FILE,
    PROTECTED_DATABASES,
    MOVEFILE_WRITE_THROUGH,
    SeedSafetyError,
    SecurityViolationError,
    LockAcquisitionError,
    StagingIntegrityError,
    PublicationCollisionError,
    validate_path_safety,
    DemoDatabaseLock,
    configure_staging_connection,
    safe_wal_shutdown,
    publish_staging_database,
)


# ── 1. Canonical Anchors & Constant Invariants ────────────────────────────────

def test_canonical_paths_and_invariants():
    """Verifies that canonical anchors point strictly to backend/ without symlinks."""
    assert CANONICAL_BACKEND_DIR.name == "backend"
    assert CANONICAL_TARGET_DB == CANONICAL_BACKEND_DIR / "library_demo.db"
    assert CANONICAL_STAGING_DB == CANONICAL_BACKEND_DIR / "library_demo.db.staging"
    assert CANONICAL_LOCK_FILE == CANONICAL_BACKEND_DIR / ".library_demo.lock"

    # Protected databases must include backend/library.db and root library.db
    assert (CANONICAL_BACKEND_DIR / "library.db").resolve() in PROTECTED_DATABASES
    assert (CANONICAL_BACKEND_DIR.parent / "library.db").resolve() in PROTECTED_DATABASES


# ── 2. Path Validation & Containment Tests ────────────────────────────────────

def test_validate_path_safety_rejects_protected_databases():
    """Ensures protected production/development databases are strictly rejected."""
    with pytest.raises(SecurityViolationError) as exc_backend:
        validate_path_safety(CANONICAL_BACKEND_DIR / "library.db")
    assert "protected database" in str(exc_backend.value).lower()

    with pytest.raises(SecurityViolationError) as exc_root:
        validate_path_safety(CANONICAL_BACKEND_DIR.parent / "library.db")
    assert "protected database" in str(exc_root.value).lower()


def test_validate_path_safety_rejects_external_and_traversal_paths(tmp_path: Path):
    """Ensures paths outside the designated backend directory are rejected."""
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()

    # Traversal to parent
    with pytest.raises(SecurityViolationError) as exc_traversal:
        validate_path_safety(fake_backend / ".." / "library_demo.db", expected_backend_dir=fake_backend)
    assert "containment violation" in str(exc_traversal.value).lower()

    # Arbitrary outside directory
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    with pytest.raises(SecurityViolationError) as exc_outside:
        validate_path_safety(outside_dir / "library_demo.db", expected_backend_dir=fake_backend)
    assert "containment violation" in str(exc_outside.value).lower()


def test_validate_path_safety_rejects_disallowed_filenames(tmp_path: Path):
    """Ensures only permitted filenames can be targeted."""
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()

    # Disallowed name
    with pytest.raises(SecurityViolationError) as exc_name:
        validate_path_safety(fake_backend / "custom_target.db", expected_backend_dir=fake_backend)
    assert "invalid target filename" in str(exc_name.value).lower()

    # Staging name disallowed when allow_staging=False
    with pytest.raises(SecurityViolationError) as exc_staging:
        validate_path_safety(
            fake_backend / "library_demo.db.staging",
            expected_backend_dir=fake_backend,
            allow_staging=False,
        )
    assert "invalid target filename" in str(exc_staging.value).lower()

    # Staging name accepted when allow_staging=True
    valid_staging = validate_path_safety(
        fake_backend / "library_demo.db.staging",
        expected_backend_dir=fake_backend,
        allow_staging=True,
    )
    assert valid_staging.name == "library_demo.db.staging"

    # Lockfile accepted when allow_lock=True
    valid_lock = validate_path_safety(
        fake_backend / ".library_demo.lock",
        expected_backend_dir=fake_backend,
        allow_lock=True,
    )
    assert valid_lock.name == ".library_demo.lock"


def test_validate_path_safety_rejects_symlinks(tmp_path: Path):
    """Verifies that symlinks in any path component are strictly rejected."""
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    real_target = fake_backend / "library_demo.db"
    symlink_target = fake_backend / "symlink_demo.db"

    try:
        symlink_target.symlink_to(real_target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted or supported in this test environment.")

    with pytest.raises(SecurityViolationError) as exc_symlink:
        validate_path_safety(symlink_target, expected_backend_dir=fake_backend)
    assert "symlink or reparse point" in str(exc_symlink.value).lower()


def test_validate_path_safety_rejects_windows_junctions(tmp_path: Path):
    """
    Verifies that NTFS directory junctions are detected and strictly rejected
    by validate_path_safety on Windows without requiring administrative privileges.
    """
    if os.name != 'nt':
        pytest.skip("Windows junction test only runs on Windows (nt).")

    real_backend = tmp_path / "real_backend"
    real_backend.mkdir()
    junction_backend = tmp_path / "junction_backend"

    # Create directory junction: junction_backend -> real_backend
    res = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction_backend), str(real_backend)],
        capture_output=True,
    )
    if res.returncode != 0:
        pytest.skip(f"mklink /J failed: {res.stderr.decode()}")

    try:
        target_through_junction = junction_backend / "library_demo.db"
        with pytest.raises(SecurityViolationError) as exc_info:
            validate_path_safety(target_through_junction, expected_backend_dir=junction_backend)
        assert "symlink or reparse point" in str(exc_info.value).lower()
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junction_backend)], capture_output=True)


# ── 3. Kernel Locking Tests ───────────────────────────────────────────────────

def test_lock_lifecycle_normal_exit_preserves_lockfile(tmp_path: Path):
    """
    Verifies that DemoDatabaseLock:
    1. Creates and locks .library_demo.lock.
    2. Writes provenance metadata (PID).
    3. Releases kernel lock upon exit.
    4. NEVER deletes the lockfile on exit.
    """
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    lock_file = fake_backend / ".library_demo.lock"

    assert not lock_file.exists()

    with DemoDatabaseLock(lock_path=lock_file, expected_backend_dir=fake_backend) as lock:
        assert lock_file.exists()
        assert lock._fd is not None

    # After context exit: lockfile STILL exists (never deleted!), but lock descriptor is closed
    assert lock_file.exists()
    assert lock._fd is None

    # Provenance metadata readable once lock handle is closed
    content = lock_file.read_text(encoding="utf-8")
    assert f'"pid": {os.getpid()}' in content

    # Immediate re-acquisition on same lockfile succeeds without error
    with DemoDatabaseLock(lock_path=lock_file, expected_backend_dir=fake_backend) as lock2:
        assert lock2._fd is not None


def test_lock_contention_blocks_second_process(tmp_path: Path):
    """
    Verifies that while one process holds the OS kernel lock, a second process
    attempting to acquire it is rejected with LockAcquisitionError.
    """
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    lock_file = fake_backend / ".library_demo.lock"

    backend_str = str(CANONICAL_BACKEND_DIR).replace('\\', '\\\\')
    lock_str = str(lock_file).replace('\\', '\\\\')
    fake_backend_str = str(fake_backend).replace('\\', '\\\\')

    # Acquire lock in parent
    with DemoDatabaseLock(lock_path=lock_file, expected_backend_dir=fake_backend):
        # Child process attempts non-blocking acquire and must fail
        child_code = f"""
import sys
sys.path.insert(0, r"{backend_str}")
from pathlib import Path
from app.seed_data.safety import DemoDatabaseLock, LockAcquisitionError

try:
    with DemoDatabaseLock(lock_path=Path(r"{lock_str}"), expected_backend_dir=Path(r"{fake_backend_str}")):
        sys.exit(0)  # Should not reach here!
except LockAcquisitionError:
    sys.exit(42)  # Expected: rejected by kernel lock
except Exception as e:
    sys.exit(1)
"""
        proc = subprocess.run(
            [sys.executable, "-c", child_code],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 42, f"Child process did not exit with 42: {proc.stderr}"


def test_lock_released_on_abrupt_process_termination(tmp_path: Path):
    """
    Verifies that if a process holding the lock exits or terminates abruptly,
    the OS kernel releases the lock automatically and another process can acquire it.
    """
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    lock_file = fake_backend / ".library_demo.lock"

    backend_str = str(CANONICAL_BACKEND_DIR).replace('\\', '\\\\')
    lock_str = str(lock_file).replace('\\', '\\\\')
    fake_backend_str = str(fake_backend).replace('\\', '\\\\')

    child_code = f"""
import sys
sys.path.insert(0, r"{backend_str}")
from pathlib import Path
from app.seed_data.safety import DemoDatabaseLock

lock = DemoDatabaseLock(lock_path=Path(r"{lock_str}"), expected_backend_dir=Path(r"{fake_backend_str}"))
lock.acquire()
# Exit immediately without calling release()
sys.exit(0)
"""
    proc = subprocess.run([sys.executable, "-c", child_code], capture_output=True)
    assert proc.returncode == 0
    assert lock_file.exists()

    # Now the parent process must be able to acquire the existing lockfile immediately
    with DemoDatabaseLock(lock_path=lock_file, expected_backend_dir=fake_backend) as lock:
        assert lock._fd is not None


# ── 4. Staging SQLite Configuration & Safe WAL Shutdown ───────────────────────

def test_configure_staging_connection_pragmas(tmp_path: Path):
    """Verifies that configure_staging_connection sets WAL, synchronous=NORMAL, foreign_keys=ON."""
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    staging_file = fake_backend / "library_demo.db.staging"

    conn = configure_staging_connection(staging_file, expected_backend_dir=fake_backend)
    try:
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk == 1

        jm = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert str(jm).lower() == "wal"

        sync = conn.execute("PRAGMA synchronous;").fetchone()[0]
        # NORMAL synchronous is numeric 1
        assert sync in (1, "NORMAL")
    finally:
        conn.close()


def test_safe_wal_shutdown_protocol(tmp_path: Path):
    """
    Verifies that safe_wal_shutdown:
    1. Truncates WAL.
    2. Switches journal mode to DELETE.
    3. Leaves no -wal or -shm sidecar files.
    """
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    staging_file = fake_backend / "library_demo.db.staging"

    # Create staging database with data in WAL mode
    conn = configure_staging_connection(staging_file, expected_backend_dir=fake_backend)
    conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, note TEXT);")
    conn.execute("INSERT INTO test_data (note) VALUES ('safe test record');")
    conn.commit()
    conn.close()

    # Run safe WAL shutdown
    safe_wal_shutdown(staging_file, expected_backend_dir=fake_backend)

    # Check sidecars are eliminated
    assert not Path(f"{staging_file}-wal").exists()
    assert not Path(f"{staging_file}-shm").exists()

    # Verify database can be opened directly and journal mode is DELETE
    verify_conn = sqlite3.connect(str(staging_file))
    try:
        jm = verify_conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert str(jm).lower() == "delete"
        row = verify_conn.execute("SELECT note FROM test_data WHERE id=1;").fetchone()
        assert row[0] == "safe test record"
    finally:
        verify_conn.close()


def test_safe_wal_shutdown_detects_lingering_sidecars(tmp_path: Path, monkeypatch):
    """Verifies that an error is raised if sidecars fail to clear after shutdown."""
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    staging_file = fake_backend / "library_demo.db.staging"

    conn = configure_staging_connection(staging_file, expected_backend_dir=fake_backend)
    conn.execute("CREATE TABLE dummy (x INT);")
    conn.commit()
    conn.close()

    orig_exists = Path.exists
    wal_sidecar = Path(f"{staging_file}-wal")

    def mock_exists(self):
        if self == wal_sidecar:
            return True
        return orig_exists(self)

    monkeypatch.setattr(Path, "exists", mock_exists)

    with pytest.raises(StagingIntegrityError) as exc:
        safe_wal_shutdown(staging_file, expected_backend_dir=fake_backend)
    assert "sidecar file" in str(exc.value).lower()


# ── 5. Atomic No-Overwrite Publication Tests ──────────────────────────────────

def test_atomic_publication_success(tmp_path: Path):
    """Verifies successful publication of staging database to target database."""
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    staging_file = fake_backend / "library_demo.db.staging"
    target_file = fake_backend / "library_demo.db"

    # Setup staging DB with clean DELETE journal mode
    conn = configure_staging_connection(staging_file, expected_backend_dir=fake_backend)
    conn.execute("CREATE TABLE books (id INT PRIMARY KEY, title TEXT);")
    conn.execute("INSERT INTO books VALUES (1, 'Published Title');")
    conn.commit()
    conn.close()

    safe_wal_shutdown(staging_file, expected_backend_dir=fake_backend)

    assert staging_file.exists()
    assert not target_file.exists()

    # Publish
    publish_staging_database(staging_file, target_file, expected_backend_dir=fake_backend)

    assert target_file.exists()
    assert not staging_file.exists()

    # Verify published data
    target_conn = sqlite3.connect(str(target_file))
    try:
        title = target_conn.execute("SELECT title FROM books WHERE id=1;").fetchone()[0]
        assert title == "Published Title"
    finally:
        target_conn.close()


def test_atomic_publication_collision_refuses_overwrite(tmp_path: Path):
    """
    Verifies that publish_staging_database strictly refuses to overwrite
    an existing target database, raising PublicationCollisionError and preserving
    both the existing target and staging database.
    """
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    staging_file = fake_backend / "library_demo.db.staging"
    target_file = fake_backend / "library_demo.db"

    # Pre-existing target file
    target_file.write_text("PRE-EXISTING VALUABLE DATA", encoding="utf-8")

    # Staging database
    conn = configure_staging_connection(staging_file, expected_backend_dir=fake_backend)
    conn.execute("CREATE TABLE staged (x INT);")
    conn.commit()
    conn.close()
    safe_wal_shutdown(staging_file, expected_backend_dir=fake_backend)

    # Attempt to publish must fail with PublicationCollisionError
    with pytest.raises(PublicationCollisionError) as exc_info:
        publish_staging_database(staging_file, target_file, expected_backend_dir=fake_backend)

    assert "already exists" in str(exc_info.value).lower()

    # Confirm NEITHER file was modified or deleted
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "PRE-EXISTING VALUABLE DATA"
    assert staging_file.exists()


def test_atomic_publication_rejects_unresolved_sidecars(tmp_path: Path):
    """Verifies that publication aborts immediately if WAL/SHM sidecars exist."""
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    staging_file = fake_backend / "library_demo.db.staging"
    target_file = fake_backend / "library_demo.db"

    staging_file.write_text("dummy db", encoding="utf-8")
    Path(f"{staging_file}-wal").write_text("dummy wal", encoding="utf-8")

    with pytest.raises(StagingIntegrityError) as exc:
        publish_staging_database(staging_file, target_file, expected_backend_dir=fake_backend)
    assert "sidecars exist" in str(exc.value).lower()
