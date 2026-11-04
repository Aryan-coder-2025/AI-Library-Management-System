"""Safety and integrity infrastructure for synthetic data generation and seeding.

This module enforces strict path security, kernel-level locking, staging isolation,
WAL shutdown protocols, and atomic no-overwrite publication to prevent corruption
or accidental modification of existing databases (e.g. library.db).
"""
import ctypes
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Canonical Anchors & Protected Targets ─────────────────────────────────────

# safety.py is located at backend/app/seed_data/safety.py
# .parents[0] -> backend/app/seed_data
# .parents[1] -> backend/app
# .parents[2] -> backend
CANONICAL_BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
CANONICAL_TARGET_DB: Path = CANONICAL_BACKEND_DIR / "library_demo.db"
CANONICAL_STAGING_DB: Path = CANONICAL_BACKEND_DIR / "library_demo.db.staging"
CANONICAL_LOCK_FILE: Path = CANONICAL_BACKEND_DIR / ".library_demo.lock"

# Absolute protected paths that must NEVER be modified or targeted
PROTECTED_DATABASES: Set[Path] = {
    (CANONICAL_BACKEND_DIR / "library.db").resolve(),
    (CANONICAL_BACKEND_DIR.parent / "library.db").resolve(),
}

# Win32 API Constants for MoveFileExW
MOVEFILE_REPLACE_EXISTING: int = 0x1
MOVEFILE_COPY_ALLOWED: int = 0x2
MOVEFILE_DELAY_UNTIL_REBOOT: int = 0x4
MOVEFILE_WRITE_THROUGH: int = 0x8
ERROR_ALREADY_EXISTS: int = 183
ERROR_FILE_EXISTS: int = 80


# ── Custom Exceptions ─────────────────────────────────────────────────────────

class SeedSafetyError(Exception):
    """Base exception for all seeding safety violations."""
    pass


class SecurityViolationError(SeedSafetyError):
    """Raised when a path safety or access boundary violation is detected."""
    pass


class LockAcquisitionError(SeedSafetyError):
    """Raised when the demo database lock cannot be acquired."""
    pass


class StagingIntegrityError(SeedSafetyError):
    """Raised when staging database configuration or shutdown fails integrity checks."""
    pass


class PublicationCollisionError(SeedSafetyError):
    """Raised when publication cannot proceed because target database already exists."""
    pass


# ── Path Security Inspection ──────────────────────────────────────────────────

def _is_reparse_point_or_junction(path: Path) -> bool:
    """Checks whether path is an NTFS junction, symlink, or other reparse point."""
    if not path.exists() and not path.is_symlink():
        return False

    if path.is_symlink():
        return True

    if os.name == 'nt':
        try:
            stat_res = os.lstat(str(path))
            # FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
            file_attrs = getattr(stat_res, "st_file_attributes", 0)
            if file_attrs & 0x0400 != 0:
                return True
            reparse_tag = getattr(stat_res, "st_reparse_tag", 0)
            if reparse_tag != 0:
                return True
        except (OSError, ValueError):
            return True

    return False


def validate_path_safety(
    target_path: Path,
    expected_backend_dir: Optional[Path] = None,
    allow_staging: bool = False,
    allow_lock: bool = False,
) -> Path:
    """
    Strictly validates that target_path:
    1. Resides directly inside expected_backend_dir (defaults to CANONICAL_BACKEND_DIR).
    2. Contains no symlinks, junctions, or reparse points in any path component.
    3. Matches only allowed target names ('library_demo.db', staging, or lock).
    4. Does NOT match any protected production/development database.
    """
    backend_anchor = (expected_backend_dir or CANONICAL_BACKEND_DIR).resolve()

    # Reject protected databases immediately
    try:
        resolved_target = target_path.resolve()
    except Exception as exc:
        raise SecurityViolationError(f"Cannot resolve path '{target_path}': {exc}") from exc

    if resolved_target in PROTECTED_DATABASES:
        raise SecurityViolationError(
            f"Access Denied: Path '{target_path}' resolves to protected database '{resolved_target}'."
        )

    # Check for symlinks and junctions along every component of target_path
    curr = target_path
    while curr != curr.parent:
        if _is_reparse_point_or_junction(curr):
            raise SecurityViolationError(
                f"Security violation: path component '{curr}' is a symlink or reparse point."
            )
        curr = curr.parent

    # Check parent directory containment
    target_parent = target_path.parent.resolve()
    if target_parent != backend_anchor:
        raise SecurityViolationError(
            f"Path containment violation: '{target_path}' parent '{target_parent}' "
            f"does not match expected backend directory '{backend_anchor}'."
        )

    # Validate target filename
    allowed_names = {"library_demo.db"}
    if allow_staging:
        allowed_names.add("library_demo.db.staging")
    if allow_lock:
        allowed_names.add(".library_demo.lock")

    if target_path.name not in allowed_names:
        raise SecurityViolationError(
            f"Invalid target filename '{target_path.name}'. Allowed filenames: {sorted(allowed_names)}."
        )

    return target_path


# ── Kernel-Level Database Lock ────────────────────────────────────────────────

class DemoDatabaseLock:
    """
    Manages mutual exclusion for demo database seeding via OS-level file locking.
    Uses msvcrt.locking on Windows and fcntl.flock on POSIX.
    
    Safety Invariants:
    - Verifies lockfile descriptor matches path identity (prevents symlink substitution).
    - NEVER deletes stale lockfiles (ownership is strictly kernel lock state).
    - Automatically releases kernel lock on normal context exit or process termination.
    """

    def __init__(
        self,
        lock_path: Optional[Path] = None,
        expected_backend_dir: Optional[Path] = None,
    ):
        self.backend_dir = (expected_backend_dir or CANONICAL_BACKEND_DIR).resolve()
        self.lock_path = (lock_path or (self.backend_dir / ".library_demo.lock")).resolve()
        self._fd: Optional[int] = None

    def acquire(self) -> None:
        if self._fd is not None:
            return  # Already acquired in this instance

        # Validate lock path safety
        validate_path_safety(
            self.lock_path,
            expected_backend_dir=self.backend_dir,
            allow_lock=True,
        )

        open_flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_BINARY"):
            open_flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            open_flags |= os.O_NOFOLLOW

        try:
            fd = os.open(str(self.lock_path), open_flags, 0o600)
        except OSError as exc:
            raise LockAcquisitionError(f"Failed to open lockfile '{self.lock_path}': {exc}") from exc

        # Verify descriptor identity matches filesystem path (anti-TOCTOU)
        try:
            fd_stat = os.fstat(fd)
            path_stat = os.lstat(str(self.lock_path))
            if fd_stat.st_dev != path_stat.st_dev or fd_stat.st_ino != path_stat.st_ino:
                os.close(fd)
                raise SecurityViolationError(
                    "Lockfile descriptor and filesystem path identity mismatch (substitution attack)."
                )
        except Exception as exc:
            os.close(fd)
            raise SecurityViolationError(f"Failed to verify lockfile identity: {exc}") from exc

        # OS-level non-blocking exclusive lock
        try:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                # Lock first byte non-blocking
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError) as exc:
            os.close(fd)
            raise LockAcquisitionError(
                f"Demo database seeding lock is currently held by another process: {exc}"
            ) from exc

        # Lock acquired successfully
        self._fd = fd

        # Write lock provenance metadata (for diagnostics; lockfile is NOT deleted on release)
        try:
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            meta = json.dumps({
                "pid": os.getpid(),
                "acquired_at": datetime.utcnow().isoformat() + "Z",
                "python": sys.version,
            }).encode("utf-8")
            os.write(fd, meta)
            os.fsync(fd)
        except OSError as exc:
            logger.warning("Could not write lock metadata: %s", exc)

    def release(self) -> None:
        if self._fd is None:
            return

        try:
            if os.name == 'nt':
                import msvcrt
                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fd, fcntl.LOCK_UN)
        except (OSError, IOError) as exc:
            logger.warning("Error unlocking demo database lock descriptor: %s", exc)
        finally:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
            # DO NOT DELETE self.lock_path: stale lockfiles are safely reused via kernel locks.

    def __enter__(self) -> "DemoDatabaseLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


# ── Staging SQLite Configuration & Safe WAL Shutdown ──────────────────────────

def configure_staging_connection(
    staging_path: Path,
    expected_backend_dir: Optional[Path] = None,
) -> sqlite3.Connection:
    """
    Safely opens and initializes a SQLite connection to the staging database.
    Validates path containment and configures essential safety PRAGMAs.
    """
    validate_path_safety(
        staging_path,
        expected_backend_dir=expected_backend_dir,
        allow_staging=True,
    )

    conn = sqlite3.connect(str(staging_path), timeout=60.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    return conn


def safe_wal_shutdown(
    staging_path: Path,
    expected_backend_dir: Optional[Path] = None,
) -> None:
    """
    Executes a strict WAL checkpoint and journal mode transition to DELETE before publication:
    1. Connects to staging database.
    2. Executes PRAGMA wal_checkpoint(TRUNCATE).
    3. Switches PRAGMA journal_mode = DELETE to eliminate WAL sidecar files.
    4. Closes connection.
    5. Confirms neither -wal nor -shm sidecar files remain.
    """
    validate_path_safety(
        staging_path,
        expected_backend_dir=expected_backend_dir,
        allow_staging=True,
    )

    if not staging_path.exists():
        raise StagingIntegrityError(f"Staging database '{staging_path}' does not exist for shutdown.")

    try:
        conn = sqlite3.connect(str(staging_path), timeout=60.0)
        try:
            # Step 1: Checkpoint WAL and truncate
            checkpoint_result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
            # Returns (busy, log_frames, checkpointed_frames)
            if checkpoint_result and checkpoint_result[0] != 0:
                raise StagingIntegrityError(
                    f"WAL checkpoint failed: database is busy (result={checkpoint_result})."
                )

            # Step 2: Switch to DELETE mode to collapse WAL sidecar into single main DB file
            mode_result = conn.execute("PRAGMA journal_mode = DELETE;").fetchone()
            if not mode_result or str(mode_result[0]).lower() != "delete":
                raise StagingIntegrityError(
                    f"Failed to switch journal mode to DELETE (current={mode_result})."
                )
        finally:
            conn.close()

    except sqlite3.Error as exc:
        raise StagingIntegrityError(f"SQLite error during safe WAL shutdown: {exc}") from exc

    # Step 3: Verify sidecars are completely gone
    wal_sidecar = Path(f"{staging_path}-wal")
    shm_sidecar = Path(f"{staging_path}-shm")

    if wal_sidecar.exists():
        raise StagingIntegrityError(
            f"Staging WAL sidecar file '{wal_sidecar}' still exists after shutdown protocol."
        )
    if shm_sidecar.exists():
        raise StagingIntegrityError(
            f"Staging SHM sidecar file '{shm_sidecar}' still exists after shutdown protocol."
        )


# ── Atomic No-Overwrite Publication ───────────────────────────────────────────

def publish_staging_database(
    staging_path: Path,
    target_path: Path,
    expected_backend_dir: Optional[Path] = None,
) -> None:
    """
    Atomically publishes staging_path to target_path with kernel-enforced NO-OVERWRITE guarantee.
    
    Platforms:
    - Windows: Win32 MoveFileExW with MOVEFILE_WRITE_THROUGH (0x8). Fails with ERROR_ALREADY_EXISTS (183)
      if target already exists. Never passes MOVEFILE_REPLACE_EXISTING.
    - POSIX: os.link(staging, target) followed by os.unlink(staging). Fails with EEXIST (17)
      if target already exists.
    
    Invariants:
    - Target database is NEVER overwritten.
    - If target exists, raises PublicationCollisionError immediately without TOCTOU race.
    - Staging database is preserved on failure.
    """
    validate_path_safety(
        staging_path,
        expected_backend_dir=expected_backend_dir,
        allow_staging=True,
    )
    validate_path_safety(
        target_path,
        expected_backend_dir=expected_backend_dir,
        allow_staging=False,
    )

    if not staging_path.exists():
        raise SeedSafetyError(f"Staging database '{staging_path}' does not exist for publication.")

    # Defense-in-depth pre-check (supplemental to kernel atomic collision enforcement)
    if target_path.exists():
        raise PublicationCollisionError(
            f"Publication target '{target_path}' already exists. Overwrite prohibited."
        )

    # Verify no staging sidecars exist prior to publish
    wal_sidecar = Path(f"{staging_path}-wal")
    shm_sidecar = Path(f"{staging_path}-shm")
    if wal_sidecar.exists() or shm_sidecar.exists():
        raise StagingIntegrityError(
            "Cannot publish staging database while WAL/SHM sidecars exist. Run safe_wal_shutdown first."
        )

    if os.name == 'nt':
        # Use Win32 MoveFileExW directly via ctypes
        move_file_ex = ctypes.windll.kernel32.MoveFileExW
        move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file_ex.restype = ctypes.c_bool

        # Crucial: NO MOVEFILE_REPLACE_EXISTING (0x1) flag! Only MOVEFILE_WRITE_THROUGH (0x8)
        success = move_file_ex(str(staging_path), str(target_path), MOVEFILE_WRITE_THROUGH)
        if not success:
            error_code = ctypes.GetLastError()
            if error_code in (ERROR_ALREADY_EXISTS, ERROR_FILE_EXISTS):
                raise PublicationCollisionError(
                    f"Kernel MoveFileExW rejected publication: destination '{target_path}' already exists "
                    f"(Win32 error={error_code})."
                )
            raise SeedSafetyError(
                f"Kernel MoveFileExW publication failed from '{staging_path}' to '{target_path}' "
                f"(Win32 error={error_code})."
            )
    else:
        # POSIX atomic link-then-unlink publication
        try:
            os.link(str(staging_path), str(target_path))
        except FileExistsError as exc:
            raise PublicationCollisionError(
                f"POSIX link rejected publication: destination '{target_path}' already exists."
            ) from exc
        except OSError as exc:
            raise SeedSafetyError(f"POSIX atomic publication link failed: {exc}") from exc

        try:
            os.unlink(str(staging_path))
        except OSError as exc:
            logger.warning("Published successfully via hard link, but failed to unlink staging file: %s", exc)

