"""
Automated Verification Suite for Stage 7 — Deterministic Embedding Population.

Validates:
1. Physical and logical embedding integrity on published backend/library_demo.db (1500/1500).
2. Raw byte format (1536 bytes/vector), float32 deserialization, finite values, and unit L2 norms.
3. Zero missing and zero stale embeddings (embedding_updated_at >= updated_at).
4. Model provenance persistence and offline snapshot matching.
5. Live semantic search functionality and monotonic descending similarity scoring.
6. Content-based recommendation generation, source book exclusion, and bounded limits.
7. AI Copilot semantic retrieval integration.
8. Librarian embedding status metrics (1500 total, 1500 embedded, 0 missing, 0 stale).
9. Protected database baseline hash immutability.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import create_access_token
from app.config import BACKEND_DIR, DEMO_SQLITE_PATH, get_settings
from app.database import get_db, get_write_db
from app.main import app


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

# Pre-verified protected baseline hashes
EXPECTED_DEV_DB_HASH = "3bd0578347ba99313fd3640669d80f66d6858ecb484a9741b206550ab906fab8"
EXPECTED_ROOT_DB_HASH = "fd764e0b0b5eda1ab0abe932055ee8b2d0e843001571f169760f9d32850d7931"
EXPECTED_MODEL_SNAPSHOT = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


@pytest.fixture(scope="module")
def demo_db_session_factory():
    """Provides sessions bound directly to backend/library_demo.db."""
    assert DEMO_SQLITE_PATH.is_file(), f"Demo database missing at {DEMO_SQLITE_PATH}"
    engine = create_engine(
        f"sqlite:///{DEMO_SQLITE_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session


@pytest.fixture
def demo_client(demo_db_session_factory):
    """TestClient wired directly to backend/library_demo.db."""
    def override_get_db():
        session = demo_db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_write_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_write_db, None)


@pytest.fixture
def student_auth_headers():
    token = create_access_token(user_id=10, role="student")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def librarian_auth_headers():
    token = create_access_token(user_id=1, role="librarian")
    return {"Authorization": f"Bearer {token}"}


# ── 1. Physical & Logical Embedding Integrity Tests ──────────────────────────

def test_demo_database_embedding_completeness():
    """Asserts 100% of books in library_demo.db have non-null embeddings."""
    conn = sqlite3.connect(str(DEMO_SQLITE_PATH))
    cur = conn.cursor()

    total_books = cur.execute("SELECT COUNT(*) FROM books;").fetchone()[0]
    non_null_emb = cur.execute("SELECT COUNT(embedding) FROM books;").fetchone()[0]
    null_emb = cur.execute("SELECT COUNT(*) FROM books WHERE embedding IS NULL;").fetchone()[0]
    conn.close()

    assert total_books == 1500, f"Expected 1,500 books, found {total_books}"
    assert non_null_emb == 1500, f"Expected 1,500 non-null embeddings, found {non_null_emb}"
    assert null_emb == 0, f"Expected 0 null embeddings, found {null_emb}"


def test_demo_database_vector_dimensions_and_finite_norms():
    """Asserts all 1,500 embeddings are 1,536-byte raw float32 buffers with norm ≈ 1.0."""
    conn = sqlite3.connect(str(DEMO_SQLITE_PATH))
    cur = conn.cursor()
    rows = cur.execute("SELECT id, embedding FROM books ORDER BY id ASC;").fetchall()
    conn.close()

    assert len(rows) == 1500

    norms = []
    for book_id, raw_emb in rows:
        assert isinstance(raw_emb, bytes), f"Book {book_id} embedding is not raw bytes"
        assert len(raw_emb) == 1536, f"Book {book_id} raw bytes length {len(raw_emb)} != 1536"

        vec = np.frombuffer(raw_emb, dtype=np.float32)
        assert vec.shape == (384,), f"Book {book_id} vector shape {vec.shape} != (384,)"
        assert np.all(np.isfinite(vec)), f"Book {book_id} vector contains non-finite values"

        norm = float(np.linalg.norm(vec))
        norms.append(norm)
        assert abs(norm - 1.0) < 1e-4, f"Book {book_id} vector norm {norm} is not unit normalized"

    avg_norm = sum(norms) / len(norms)
    assert abs(avg_norm - 1.0) < 1e-5


def test_demo_database_embedding_freshness():
    """Asserts all 1,500 books have embedding_updated_at >= updated_at."""
    conn = sqlite3.connect(str(DEMO_SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute("SELECT id, updated_at, embedding_updated_at FROM books;").fetchall()
    conn.close()

    assert len(rows) == 1500
    stale_count = 0

    for r in rows:
        assert r["embedding_updated_at"] is not None, f"Book {r['id']} has NULL embedding_updated_at"
        up_at = datetime.fromisoformat(r["updated_at"])
        emb_up_at = datetime.fromisoformat(r["embedding_updated_at"])
        if emb_up_at < up_at:
            stale_count += 1

    assert stale_count == 0, f"Found {stale_count} stale embeddings in library_demo.db"


def test_embedding_provenance_file():
    """Asserts that provenance metadata exists and matches expected model snapshot."""
    prov_path = BACKEND_DIR / "app" / "seed_data" / "embedding_provenance.json"
    assert prov_path.is_file(), f"Provenance file missing at {prov_path}"

    with open(prov_path, "r", encoding="utf-8") as f:
        prov = json.load(f)

    assert prov["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert prov["model_snapshot_revision"] == EXPECTED_MODEL_SNAPSHOT
    assert prov["embedding_dimension"] == 384
    assert prov["vector_bytes_per_book"] == 1536
    assert prov["total_books_embedded"] == 1500
    assert 0.999 < prov["avg_vector_norm"] < 1.001


# ── 2. End-to-End Semantic Search Tests ───────────────────────────────────────

def test_semantic_search_distributed_systems(demo_client, student_auth_headers):
    """Executes semantic search for 'Distributed Systems' and asserts descending scores."""
    response = demo_client.get(
        "/api/search/semantic?q=Distributed+Systems+and+Cloud+Architecture&page_size=10",
        headers=student_auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total"] > 0
    items = data["items"]
    assert len(items) > 0

    # Verify descending similarity scores
    scores = [item["similarity_score"] for item in items]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], f"Ranking violation: {scores[i]} < {scores[i+1]}"

    # Verify bounded score range
    assert all(-1.0 <= s <= 1.0 for s in scores)
    # The top result should have substantial semantic affinity
    assert scores[0] > 0.35, f"Top similarity score too low: {scores[0]}"

    # Verify book structure
    for item in items:
        assert item["id"] > 0
        assert item["title"]
        assert item["author"]
        assert item["category"]


def test_semantic_search_diverse_queries(demo_client, student_auth_headers):
    """Tests varied queries spanning multiple domains."""
    queries = [
        "Quantum Computing algorithms and entanglement",
        "European Renaissance history and art",
        "Organic chemistry synthesis and reaction mechanisms",
    ]
    for q in queries:
        resp = demo_client.get(
            f"/api/search/semantic?q={q}&page_size=5",
            headers=student_auth_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        scores = [item["similarity_score"] for item in items]
        assert scores == sorted(scores, reverse=True)


# ── 3. End-to-End Content Recommendations Tests ──────────────────────────────

def test_content_recommendations_for_book(demo_client, student_auth_headers):
    """Verifies content-based recommendations for book ID 1."""
    target_book_id = 1
    resp = demo_client.get(
        f"/api/books/{target_book_id}/recommendations?limit=5",
        headers=student_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["source_book_id"] == target_book_id
    recs = data["recommendations"]
    assert 1 <= len(recs) <= 5

    # Source book must be strictly excluded
    rec_ids = [r["id"] for r in recs]
    assert target_book_id not in rec_ids, "Source book was returned in its own recommendations!"

    # Cosine similarities must be descending
    sim_scores = [r["similarity_score"] for r in recs]
    for i in range(len(sim_scores) - 1):
        assert sim_scores[i] >= sim_scores[i + 1]
    assert all(-1.0 <= s <= 1.0 for s in sim_scores)


def test_content_recommendations_nonexistent_book(demo_client, student_auth_headers):
    """Verifies 404 is returned when requesting recommendations for an invalid book ID."""
    resp = demo_client.get(
        "/api/books/999999/recommendations",
        headers=student_auth_headers,
    )
    assert resp.status_code == 404


# ── 4. Embedding Status Metrics Endpoint Tests ────────────────────────────────

def test_embedding_status_endpoint(demo_client, librarian_auth_headers):
    """Verifies /api/embeddings/status reports 1,500 total, 1,500 embedded, 0 missing, 0 stale."""
    resp = demo_client.get(
        "/api/embeddings/status",
        headers=librarian_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["total_books"] == 1500
    assert data["with_embedding"] == 1500
    assert data["missing_embedding"] == 0
    assert data["stale_embedding"] == 0
    assert data["model_available"] is True


# ── 5. AI Copilot Semantic Integration Tests ──────────────────────────────────

def test_copilot_semantic_book_search(demo_client, student_auth_headers):
    """Verifies Copilot leverages semantic search for catalogue queries."""
    csrf_val = "demo-copilot-csrf-token"
    demo_client.cookies.set("csrf_token", csrf_val)
    headers = {
        **student_auth_headers,
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": csrf_val,
    }

    payload = {
        "message": "Can you recommend books about operating systems or distributed computing?",
        "history": [],
    }
    resp = demo_client.post(
        "/api/copilot/chat",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert len(data["reply"]) > 0
    # Must retrieve relevant source citations
    sources = data.get("sources", [])
    assert len(sources) > 0
    assert any(s["type"] == "book" for s in sources)


# ── 6. Protected Database Safety Assertions ───────────────────────────────────

def test_protected_databases_remain_untouched():
    """Guarantees both protected databases were completely untouched by Stage 7."""
    dev_db = BACKEND_DIR / "library.db"
    root_db = BACKEND_DIR.parent / "library.db"

    assert dev_db.is_file(), f"Development DB missing at {dev_db}"
    assert root_db.is_file(), f"Root DB missing at {root_db}"

    actual_dev_hash = compute_sha256(dev_db)
    actual_root_hash = compute_sha256(root_db)

    assert actual_dev_hash == EXPECTED_DEV_DB_HASH, (
        f"Protected dev DB hash corrupted: expected {EXPECTED_DEV_DB_HASH}, got {actual_dev_hash}"
    )
    assert actual_root_hash == EXPECTED_ROOT_DB_HASH, (
        f"Protected root DB hash corrupted: expected {EXPECTED_ROOT_DB_HASH}, got {actual_root_hash}"
    )
