"""
Deterministic Vector Embedding Generator for AI Library Management System (Stage 7).

Generates 384-dimensional normalized float32 semantic embeddings for all 1,500 monographs
in backend/library_demo.db using sentence-transformers/all-MiniLM-L6-v2.

Safety & Integrity Guarantees:
1. Operates under OS-level DemoDatabaseLock.
2. Verified against Stage 7A preflight baseline hashes.
3. Protected databases (backend/library.db and root library.db) are NEVER touched.
4. Generates embeddings exclusively in an isolated staging database (library_demo.db.staging).
5. Enforces zero data skipping: exactly 1,500 books must receive valid 384-d normalized vectors.
6. Enforces embedding_updated_at >= updated_at to eliminate stale embeddings.
7. Executes safe WAL shutdown (PRAGMA journal_mode = DELETE) before atomic publication.
8. Retains a recoverable pre-stage7 backup of library_demo.db.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Dict, List, Tuple

import numpy as np

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import (
    DEFAULT_SQLITE_PATH,
    ROOT_SQLITE_PATH,
    DEMO_SQLITE_PATH,
)
from app.seed_data.safety import (
    DemoDatabaseLock,
    safe_wal_shutdown,
    publish_staging_database,
    validate_path_safety,
    SecurityViolationError,
    SeedSafetyError,
)
from app.services.embedding import (
    build_book_document,
    serialize_vector,
    deserialize_vector,
    MODEL_NAME,
    EMBEDDING_DIM,
)

# Provenance invariants
EXPECTED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EXPECTED_COMMIT_SNAPSHOT = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EXPECTED_VECTOR_BYTES = 1536  # 384 * 4 bytes (float32)
EXPECTED_TOTAL_BOOKS = 1500

# Cryptographic baseline hashes
EXPECTED_PROD_DB_HASH = "3bd0578347ba99313fd3640669d80f66d6858ecb484a9741b206550ab906fab8"
EXPECTED_ROOT_DB_HASH = "fd764e0b0b5eda1ab0abe932055ee8b2d0e843001571f169760f9d32850d7931"
EXPECTED_DEMO_PRE_HASH = "df59eba1c765457e5129b5be08917bc4049d7ff250ea4aa080010ad9655c3bd3"


def compute_sha256(path: Path) -> str:
    """Computes SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_model_provenance() -> None:
    """Verifies that the exact local model snapshot is present offline."""
    from sentence_transformers import SentenceTransformer

    # 1. Verify model cache snapshot on disk
    user_home = Path.home()
    hub_dir = user_home / ".cache" / "huggingface" / "hub" / "models--sentence-transformers--all-MiniLM-L6-v2"
    ref_main = hub_dir / "refs" / "main"
    if ref_main.is_file():
        commit = ref_main.read_text(encoding="utf-8").strip()
        if commit != EXPECTED_COMMIT_SNAPSHOT:
            raise SeedSafetyError(
                f"Model snapshot revision mismatch: found '{commit}', expected '{EXPECTED_COMMIT_SNAPSHOT}'."
            )
        print(f"[PREFLIGHT] Model snapshot verified on disk: {commit}")
    else:
        print("[PREFLIGHT] Notice: HF cache ref file not present; verifying via offline loader.")

    # 2. Verify model loads with local_files_only=True
    try:
        model = SentenceTransformer(EXPECTED_MODEL_NAME, local_files_only=True)
    except Exception as exc:
        raise SeedSafetyError(f"Failed to load embedding model offline: {exc}") from exc

    dim = model.get_sentence_embedding_dimension()
    if dim != EMBEDDING_DIM:
        raise SeedSafetyError(f"Model embedding dimension mismatch: got {dim}, expected {EMBEDDING_DIM}.")
    print(f"[PREFLIGHT] Model '{EXPECTED_MODEL_NAME}' successfully verified offline (dim={dim}).")


def populate_demo_embeddings(
    batch_size: int = 64,
    verify_only: bool = False,
) -> Dict[str, any]:
    """
    Main orchestration routine for Stage 7 embedding generation.
    """
    start_time = datetime.utcnow()
    backend_dir = BACKEND_DIR.resolve()
    canonical_demo_db = (backend_dir / "library_demo.db").resolve()
    staging_path = (backend_dir / "library_demo.db.staging").resolve()
    backup_path = (backend_dir / "library_demo.db.pre_stage7_backup").resolve()
    provenance_path = (backend_dir / "app" / "seed_data" / "embedding_provenance.json").resolve()

    print("=" * 80)
    print("STAGE 7: DETERMINISTIC VECTOR EMBEDDING GENERATION")
    print("=" * 80)

    with DemoDatabaseLock(expected_backend_dir=backend_dir):
        # 1. Preflight baseline verification
        print("\n--- 1. PREFLIGHT BASELINE CHECKS ---")
        prod_hash = compute_sha256(DEFAULT_SQLITE_PATH)
        root_hash = compute_sha256(ROOT_SQLITE_PATH)
        demo_hash = compute_sha256(canonical_demo_db)

        print(f"Protected Development DB: {prod_hash}")
        print(f"Protected Root DB:        {root_hash}")
        print(f"Current Demo DB:          {demo_hash}")

        if prod_hash != EXPECTED_PROD_DB_HASH:
            raise SeedSafetyError(
                f"Protected development DB hash mismatch: expected {EXPECTED_PROD_DB_HASH}, got {prod_hash}."
            )
        if root_hash != EXPECTED_ROOT_DB_HASH:
            raise SeedSafetyError(
                f"Protected root DB hash mismatch: expected {EXPECTED_ROOT_DB_HASH}, got {root_hash}."
            )
        if demo_hash != EXPECTED_DEMO_PRE_HASH:
            raise SeedSafetyError(
                f"Published demo DB hash mismatch: expected {EXPECTED_DEMO_PRE_HASH}, got {demo_hash}."
            )
        print("[PREFLIGHT] All pre-execution baseline database hashes confirmed.")

        # 2. Verify model offline provenance
        print("\n--- 2. VERIFYING MODEL PROVENANCE ---")
        verify_model_provenance()
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(EXPECTED_MODEL_NAME, local_files_only=True)

        # 3. Clean and prepare isolated staging copy
        print("\n--- 3. PREPARING ISOLATED STAGING COPY ---")
        if staging_path.exists():
            staging_path.unlink()
        for ext in ["-wal", "-shm"]:
            sidecar = Path(f"{staging_path}{ext}")
            if sidecar.exists():
                sidecar.unlink()

        shutil.copy2(canonical_demo_db, staging_path)
        validate_path_safety(staging_path, expected_backend_dir=backend_dir, allow_staging=True)
        staging_copy_hash = compute_sha256(staging_path)
        assert staging_copy_hash == EXPECTED_DEMO_PRE_HASH, "Staging copy failed SHA-256 verification!"
        print(f"Staging copy prepared: {staging_path} (SHA-256: {staging_copy_hash})")

        # 4. Generate embeddings in staging copy
        print("\n--- 4. GENERATING EMBEDDINGS IN STAGING ---")
        conn = sqlite3.connect(str(staging_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Fetch all books in ascending ID order
        books = cur.execute(
            "SELECT id, title, author, category, description, is_archived, updated_at "
            "FROM books ORDER BY id ASC;"
        ).fetchall()

        if len(books) != EXPECTED_TOTAL_BOOKS:
            raise SeedSafetyError(
                f"Book count mismatch in demo DB: found {len(books)}, expected {EXPECTED_TOTAL_BOOKS}."
            )
        print(f"Loaded {len(books)} monographs for processing.")

        # Prepare document texts and track metadata
        doc_texts: List[str] = []
        book_ids: List[int] = []
        book_updated_ats: List[str] = []

        for b in books:
            b_id = b["id"]
            title = b["title"]
            author = b["author"]
            category = b["category"]
            description = b["description"]
            up_at = b["updated_at"]

            if not title or not title.strip():
                raise SeedSafetyError(f"Book ID {b_id} has empty title.")
            if not author or not author.strip():
                raise SeedSafetyError(f"Book ID {b_id} has empty author.")
            if not category or not category.strip():
                raise SeedSafetyError(f"Book ID {b_id} has empty category.")

            doc = build_book_document(
                title=title,
                author=author,
                category=category,
                description=description,
            )
            doc_texts.append(doc)
            book_ids.append(b_id)
            book_updated_ats.append(up_at)

        # Batch encode with SentenceTransformer
        print(f"Encoding {len(doc_texts)} documents (batch_size={batch_size}, normalize=True)...")
        t_enc_start = datetime.utcnow()
        raw_embeddings = model.encode(
            doc_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        t_enc_end = datetime.utcnow()
        enc_duration = (t_enc_end - t_enc_start).total_seconds()
        print(f"Batch encoding complete in {enc_duration:.2f}s ({len(doc_texts)/enc_duration:.1f} docs/sec).")

        # Validate vector array properties
        if raw_embeddings.shape != (EXPECTED_TOTAL_BOOKS, EMBEDDING_DIM):
            raise SeedSafetyError(
                f"Unexpected embeddings shape: {raw_embeddings.shape}, expected {(EXPECTED_TOTAL_BOOKS, EMBEDDING_DIM)}."
            )
        if raw_embeddings.dtype != np.float32:
            raw_embeddings = raw_embeddings.astype(np.float32)

        # Persist vectors into staging database atomically
        print("Persisting embeddings and timestamps into staging database...")
        update_rows: List[Tuple[bytes, str, int]] = []
        norms: List[float] = []

        for idx, b_id in enumerate(book_ids):
            vec = raw_embeddings[idx]

            # Numeric assertions
            if not np.all(np.isfinite(vec)):
                raise SeedSafetyError(f"Vector for book ID {b_id} contains NaN or Infinite values.")

            norm = float(np.linalg.norm(vec))
            norms.append(norm)
            if abs(norm - 1.0) > 1e-5:
                raise SeedSafetyError(f"Vector for book ID {b_id} is not unit-normalized (norm={norm}).")

            # Serialization
            raw_bytes = serialize_vector(vec)
            if len(raw_bytes) != EXPECTED_VECTOR_BYTES:
                raise SeedSafetyError(
                    f"Serialized vector byte length mismatch for book ID {b_id}: {len(raw_bytes)} bytes (expected {EXPECTED_VECTOR_BYTES})."
                )

            # Ensure embedding_updated_at >= updated_at
            b_up_at = datetime.fromisoformat(book_updated_ats[idx]) if book_updated_ats[idx] else datetime.utcnow()
            emb_timestamp = max(datetime.utcnow(), b_up_at).isoformat()

            update_rows.append((raw_bytes, emb_timestamp, b_id))

        cur.executemany(
            "UPDATE books SET embedding = ?, embedding_updated_at = ? WHERE id = ?;",
            update_rows,
        )
        conn.commit()
        print(f"Successfully updated {len(update_rows)} book records in staging database.")

        # 5. Mandatory Verification on Staging Database
        print("\n--- 5. MANDATORY VERIFICATION ON STAGING DATABASE ---")
        non_null_cnt = cur.execute("SELECT COUNT(*) FROM books WHERE embedding IS NOT NULL;").fetchone()[0]
        null_cnt = cur.execute("SELECT COUNT(*) FROM books WHERE embedding IS NULL;").fetchone()[0]
        valid_len_cnt = cur.execute(f"SELECT COUNT(*) FROM books WHERE LENGTH(embedding) = {EXPECTED_VECTOR_BYTES};").fetchone()[0]
        stale_cnt = cur.execute("SELECT COUNT(*) FROM books WHERE embedding_updated_at < updated_at;").fetchone()[0]
        valid_timestamp_cnt = cur.execute("SELECT COUNT(*) FROM books WHERE embedding_updated_at >= updated_at;").fetchone()[0]

        print(f"Non-NULL embeddings:   {non_null_cnt} / {EXPECTED_TOTAL_BOOKS}")
        print(f"NULL embeddings:       {null_cnt}")
        print(f"Valid 1536-byte len:   {valid_len_cnt} / {EXPECTED_TOTAL_BOOKS}")
        print(f"Stale embeddings:      {stale_cnt}")
        print(f"Current embeddings:    {valid_timestamp_cnt} / {EXPECTED_TOTAL_BOOKS}")

        if non_null_cnt != EXPECTED_TOTAL_BOOKS:
            raise SeedSafetyError(f"Embedding population incomplete: {non_null_cnt} populated, expected {EXPECTED_TOTAL_BOOKS}.")
        if null_cnt != 0:
            raise SeedSafetyError(f"Found {null_cnt} books with NULL embeddings.")
        if valid_len_cnt != EXPECTED_TOTAL_BOOKS:
            raise SeedSafetyError(f"Found books with invalid vector byte lengths (expected {EXPECTED_TOTAL_BOOKS}).")
        if stale_cnt != 0:
            raise SeedSafetyError(f"Found {stale_cnt} stale embeddings in staging database.")

        # Integrity checks
        quick_check = [r[0] for r in cur.execute("PRAGMA quick_check;").fetchall()]
        if quick_check != ["ok"]:
            raise SeedSafetyError(f"Staging quick_check failed: {quick_check}")
        fk_check = cur.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_check:
            raise SeedSafetyError(f"Staging foreign_key_check failed: {len(fk_check)} violations.")
        print("PRAGMA quick_check = ok | PRAGMA foreign_key_check = 0 violations.")

        # Spot-check deserialization across all 1,500 books
        all_stored_vecs = cur.execute("SELECT id, embedding FROM books ORDER BY id ASC;").fetchall()
        for row in all_stored_vecs:
            v = deserialize_vector(row["embedding"])
            if v.shape != (384,) or v.dtype != np.float32 or not np.all(np.isfinite(v)):
                raise SeedSafetyError(f"Deserialization check failed on book ID {row['id']}.")

        print("100% of stored vectors successfully deserialized and verified.")
        conn.close()

        # 6. Record Provenance Metadata
        print("\n--- 6. RECORDING PROVENANCE METADATA ---")
        provenance = {
            "model_name": EXPECTED_MODEL_NAME,
            "model_snapshot_revision": EXPECTED_COMMIT_SNAPSHOT,
            "embedding_dimension": EMBEDDING_DIM,
            "vector_bytes_per_book": EXPECTED_VECTOR_BYTES,
            "normalization": "L2 unit norm (||v||_2 = 1.0)",
            "total_books_embedded": EXPECTED_TOTAL_BOOKS,
            "min_vector_norm": float(min(norms)),
            "max_vector_norm": float(max(norms)),
            "avg_vector_norm": float(sum(norms) / len(norms)),
            "preprocessing_contract": "Title: {title} | Author: {author} | Category: {category} | Description: {description}",
            "serialization_contract": "float32 raw buffer bytes (1536 bytes, little-endian)",
            "generation_timestamp": datetime.utcnow().isoformat(),
            "source_database_pre_hash": EXPECTED_DEMO_PRE_HASH,
        }
        with open(provenance_path, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2)
        print(f"Provenance recorded to: {provenance_path}")

        # 7. Safe WAL Shutdown on Staging Database
        print("\n--- 7. SAFE WAL SHUTDOWN ON STAGING DATABASE ---")
        safe_wal_shutdown(staging_path, expected_backend_dir=backend_dir)
        print("Safe WAL shutdown complete. Zero sidecars remain.")

        # 8. Atomic Publication with Rollback Protection
        print("\n--- 8. ATOMIC PUBLICATION & BACKUP ---")
        if backup_path.exists():
            backup_path.unlink()

        # Create recoverable backup of the original demo database
        shutil.move(str(canonical_demo_db), str(backup_path))
        print(f"Created recoverable backup of original demo DB at: {backup_path}")

        try:
            # Atomically publish staging into canonical target
            publish_staging_database(
                staging_path=staging_path,
                target_path=canonical_demo_db,
                expected_backend_dir=backend_dir,
            )
            print(f"Staging database published atomically to: {canonical_demo_db}")

            # Re-enable WAL mode on published database
            conn_pub = sqlite3.connect(str(canonical_demo_db))
            conn_pub.execute("PRAGMA journal_mode = WAL;")
            quick_pub = conn_pub.execute("PRAGMA quick_check;").fetchall()
            fk_pub = conn_pub.execute("PRAGMA foreign_key_check;").fetchall()
            conn_pub.close()

            if [r[0] for r in quick_pub] != ["ok"]:
                raise SeedSafetyError(f"Published demo DB quick_check failed: {quick_pub}")
            if fk_pub:
                raise SeedSafetyError(f"Published demo DB foreign_key_check reported {len(fk_pub)} violations.")
            print("Published database verified with WAL mode restored.")

        except Exception as pub_err:
            print(f"[CRITICAL ERROR] Publication failed: {pub_err}. Initiating rollback...")
            if backup_path.exists():
                if canonical_demo_db.exists():
                    canonical_demo_db.unlink()
                shutil.move(str(backup_path), str(canonical_demo_db))
                print(f"[ROLLBACK] Restored original demo database from {backup_path}.")
            raise

        # 9. Post-Publication Integrity & Hash Verification
        print("\n--- 9. POST-PUBLICATION INTEGRITY VERIFICATION ---")
        post_demo_hash = compute_sha256(canonical_demo_db)
        post_demo_size = canonical_demo_db.stat().st_size
        post_prod_hash = compute_sha256(DEFAULT_SQLITE_PATH)
        post_root_hash = compute_sha256(ROOT_SQLITE_PATH)

        print(f"Published Demo DB Hash: {post_demo_hash} ({post_demo_size:,} bytes)")
        print(f"Protected Development:  {post_prod_hash}")
        print(f"Protected Root:         {post_root_hash}")

        if post_prod_hash != EXPECTED_PROD_DB_HASH:
            raise SeedSafetyError("CRITICAL: Protected development DB was altered during Stage 7!")
        if post_root_hash != EXPECTED_ROOT_DB_HASH:
            raise SeedSafetyError("CRITICAL: Protected root DB was altered during Stage 7!")

        duration = (datetime.utcnow() - start_time).total_seconds()
        print(f"\n[STAGE 7 COMPLETE] 1,500 embeddings populated and verified in {duration:.1f}s.")

        result = {
            "status": "SUCCESS",
            "total_embedded": EXPECTED_TOTAL_BOOKS,
            "pre_demo_hash": EXPECTED_DEMO_PRE_HASH,
            "post_demo_hash": post_demo_hash,
            "post_demo_size_bytes": post_demo_size,
            "backup_location": str(backup_path),
            "provenance_location": str(provenance_path),
            "duration_seconds": round(duration, 2),
            "protected_dev_hash": post_prod_hash,
            "protected_root_hash": post_root_hash,
        }
        return result


if __name__ == "__main__":
    populate_demo_embeddings()

