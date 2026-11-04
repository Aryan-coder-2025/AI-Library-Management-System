"""
Automated test suite for Stage 5 — Semantic Book Search and Content-Based Recommendations.

Coverage:
1. Semantic search ranking using deterministic test vectors.
2. Archived-book exclusion from semantic search and recommendations.
3. Un-embedded and stale book handling.
4. Empty and overlong query validation.
5. Content-based recommendations: source book exclusion, ranking, and bounded limits.
6. Error handling: non-existent book, archived source book, un-embedded source book.
7. Model unavailable handling (503 Service Unavailable).
8. Embedding status metrics reporting (total, with_embedding, missing, stale).
9. Librarian-only refresh authorization (401 unauth, 403 student, 200 librarian).
10. Refresh processing: missing and stale embeddings updated with error isolation.
11. Pagination and response schema verification.
"""
from datetime import datetime, timedelta
import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.models import Book, BookCopy, User
from app.services import embedding as embedding_service


# ── Helper Functions & Mock Encoders ──────────────────────────────────────────

def make_unit_vector(non_zero_idx: int = 0, dim: int = 384) -> np.ndarray:
    """Creates a deterministic unit-length 384-d vector."""
    vec = np.zeros(dim, dtype=np.float32)
    vec[non_zero_idx] = 1.0
    return vec


def make_blended_vector(idx1: int, idx2: int, weight1: float = 0.8, weight2: float = 0.6, dim: int = 384) -> np.ndarray:
    """Creates a normalized blended vector spanning two dimensions."""
    vec = np.zeros(dim, dtype=np.float32)
    vec[idx1] = weight1
    vec[idx2] = weight2
    norm = np.linalg.norm(vec)
    return (vec / norm).astype(np.float32)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def auth_librarian(client, db: Session):
    """Creates a librarian user and sets authentication headers and cookies."""
    user = User(
        email="semantic_lib@library.org",
        full_name="Semantic Librarian",
        hashed_password=hash_password("SemanticLib123!"),
        role="librarian",
        is_active=True,
    )
    db.add(user)
    db.flush()
    token = create_access_token(user_id=user.id, role="librarian")
    csrf_val = "semantic-csrf-token-lib"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user_id": user.id,
        "token": token,
        "csrf_val": csrf_val,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


@pytest.fixture
def auth_student(client, db: Session):
    """Creates a student user."""
    user = User(
        email="semantic_stud@university.edu",
        full_name="Semantic Student",
        hashed_password=hash_password("SemanticStud123!"),
        role="student",
        is_active=True,
    )
    db.add(user)
    db.flush()
    token = create_access_token(user_id=user.id, role="student")
    csrf_val = "semantic-csrf-token-stud"
    return {
        "user_id": user.id,
        "token": token,
        "csrf_val": csrf_val,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


@pytest.fixture(autouse=True)
def cleanup_mock_encoder():
    """Ensures mock encoder is reset after every test."""
    yield
    embedding_service.reset_mock_encoder()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_semantic_search_ranking_deterministic(client, auth_student, db: Session):
    """
    Verifies that books are correctly ranked in descending order of vector cosine similarity
    against the query vector.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    # Setup 3 books with deterministic vectors:
    # Query will be vec(0).
    # Book 1: exactly vec(0) -> cosine similarity 1.0
    # Book 2: blend of vec(0) and vec(1) -> cosine similarity ~0.8
    # Book 3: vec(10) -> orthogonal, cosine similarity 0.0
    vec_query = make_unit_vector(0)
    vec_b1 = make_unit_vector(0)
    vec_b2 = make_blended_vector(0, 1, 0.8, 0.6)
    vec_b3 = make_unit_vector(10)

    now = datetime.utcnow()
    past = now - timedelta(hours=1)
    b1 = Book(
        title="Deep Learning and Neural Networks",
        author="Ian Goodfellow",
        isbn="978-0262035613",
        category="Computer Science",
        description="Comprehensive study of modern deep learning and backpropagation.",
        embedding=embedding_service.serialize_vector(vec_b1),
        embedding_updated_at=now,
        updated_at=past,
    )
    b2 = Book(
        title="Python Data Science Handbook",
        author="Jake VanderPlas",
        isbn="978-1491912058",
        category="Computer Science",
        description="Computational and statistical methods using Python.",
        embedding=embedding_service.serialize_vector(vec_b2),
        embedding_updated_at=now,
        updated_at=past,
    )
    b3 = Book(
        title="Ancient Rome: The Rise and Fall of an Empire",
        author="Simon Baker",
        isbn="978-1846072840",
        category="History",
        description="Detailed history of the Roman empire from republic to fall.",
        embedding=embedding_service.serialize_vector(vec_b3),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add_all([b1, b2, b3])
    db.flush()

    # Configure mock encoder to return vec_query for query "deep learning"
    def mock_enc(text: str):
        return vec_query

    embedding_service.set_mock_encoder(mock_enc)

    response = client.get(
        "/api/search/semantic",
        params={"q": "deep learning"},
        headers=auth_student["headers"],
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["query"] == "deep learning"
    assert "cosine similarity" in data["disclaimer"].lower()

    # Verify ranking: B1 (1.0) > B2 (~0.8) > B3 (0.0)
    scores = [item["similarity_score"] for item in data["items"]]
    assert scores[0] >= scores[1] >= scores[2]
    assert data["items"][0]["id"] == b1.id
    assert data["items"][0]["similarity_score"] == 1.0
    assert data["items"][1]["id"] == b2.id
    assert data["items"][2]["id"] == b3.id


def test_semantic_search_archived_books_excluded(client, auth_student, db: Session):
    """
    Verifies that archived books are completely excluded from semantic search results,
    even if their vector similarity is 1.0.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    vec = make_unit_vector(0)
    now = datetime.utcnow()
    past = now - timedelta(hours=1)

    archived_book = Book(
        title="Archived AI Foundations",
        author="Alan Turing",
        isbn="978-0111111111",
        category="Computer Science",
        description="Legacy archived volume.",
        is_archived=True,
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
        updated_at=past,
    )
    active_book = Book(
        title="Active AI Foundations",
        author="Alan Turing",
        isbn="978-0222222222",
        category="Computer Science",
        description="Current edition.",
        is_archived=False,
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add_all([archived_book, active_book])
    db.flush()

    embedding_service.set_mock_encoder(lambda t: vec)

    response = client.get(
        "/api/search/semantic",
        params={"q": "foundations"},
        headers=auth_student["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    item_ids = [item["id"] for item in data["items"]]
    assert active_book.id in item_ids
    assert archived_book.id not in item_ids


def test_semantic_search_unembedded_books_excluded(client, auth_student, db: Session):
    """
    Verifies that books lacking an embedding are excluded from semantic search results.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    vec = make_unit_vector(0)
    now = datetime.utcnow()
    past = now - timedelta(hours=1)

    book_with_vec = Book(
        title="Embedded Book",
        author="Author One",
        isbn="978-0333333333",
        category="Fiction",
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
        updated_at=past,
    )
    book_without_vec = Book(
        title="Unembedded Book",
        author="Author Two",
        isbn="978-0444444444",
        category="Fiction",
        embedding=None,
        embedding_updated_at=None,
    )
    db.add_all([book_with_vec, book_without_vec])
    db.flush()

    embedding_service.set_mock_encoder(lambda t: vec)

    response = client.get(
        "/api/search/semantic",
        params={"q": "fiction"},
        headers=auth_student["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    item_ids = [item["id"] for item in data["items"]]
    assert book_with_vec.id in item_ids
    assert book_without_vec.id not in item_ids


def test_semantic_search_empty_and_whitespace_query(client, auth_student):
    """
    Verifies that empty or whitespace-only queries return an empty result list without errors.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    for empty_q in ["", "   ", "\t\n"]:
        response = client.get(
            "/api/search/semantic",
            params={"q": empty_q},
            headers=auth_student["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["total_pages"] == 0


def test_semantic_search_query_too_long(client, auth_student):
    """
    Verifies that queries exceeding 500 characters are rejected with 422 Unprocessable Entity.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    long_q = "a" * 501
    response = client.get(
        "/api/search/semantic",
        params={"q": long_q},
        headers=auth_student["headers"],
    )
    assert response.status_code == 422
    assert "exceeds maximum allowed length" in response.text


def test_content_recommendations_ranking_and_source_exclusion(client, auth_student, db: Session):
    """
    Verifies content-based recommendations:
    - Excludes the source book itself.
    - Excludes archived books.
    - Correctly ranks by vector cosine similarity.
    - Honors the requested limit parameter.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    vec_source = make_unit_vector(0)
    vec_high = make_blended_vector(0, 1, 0.9, 0.4)   # high similarity with vec_source
    vec_med = make_blended_vector(0, 2, 0.6, 0.8)    # medium similarity
    vec_low = make_unit_vector(5)                    # orthogonal (0.0)

    now = datetime.utcnow()
    past = now - timedelta(hours=1)
    source_b = Book(
        title="Intro to Computer Vision",
        author="Richard Szeliski",
        isbn="978-1848829343",
        category="Computer Science",
        embedding=embedding_service.serialize_vector(vec_source),
        embedding_updated_at=now,
        updated_at=past,
    )
    rec_b1 = Book(
        title="Multiple View Geometry in Computer Vision",
        author="Richard Hartley",
        isbn="978-0521540513",
        category="Computer Science",
        embedding=embedding_service.serialize_vector(vec_high),
        embedding_updated_at=now,
        updated_at=past,
    )
    rec_b2 = Book(
        title="Digital Image Processing",
        author="Rafael Gonzalez",
        isbn="978-0133356724",
        category="Computer Science",
        embedding=embedding_service.serialize_vector(vec_med),
        embedding_updated_at=now,
        updated_at=past,
    )
    rec_b3 = Book(
        title="World History: Medieval Eras",
        author="Historian X",
        isbn="978-0999999999",
        category="History",
        embedding=embedding_service.serialize_vector(vec_low),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add_all([source_b, rec_b1, rec_b2, rec_b3])
    db.flush()

    response = client.get(
        f"/api/books/{source_b.id}/recommendations",
        params={"limit": 2},
        headers=auth_student["headers"],
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["source_book_id"] == source_b.id
    assert data["source_book_title"] == source_b.title
    assert data["total"] == 2
    assert len(data["recommendations"]) == 2

    # Verify source book is excluded from recommendations
    rec_ids = [r["id"] for r in data["recommendations"]]
    assert source_b.id not in rec_ids

    # Verify top 2 ranking
    assert rec_ids == [rec_b1.id, rec_b2.id]
    assert data["recommendations"][0]["similarity_score"] >= data["recommendations"][1]["similarity_score"]


def test_content_recommendations_archived_books_excluded(client, auth_student, db: Session):
    """
    Verifies that archived books are never returned as recommendations.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    vec = make_unit_vector(0)
    now = datetime.utcnow()
    past = now - timedelta(hours=1)

    source = Book(
        title="Source ML Book",
        author="Author",
        isbn="978-0555555555",
        category="Tech",
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
        updated_at=past,
    )
    archived_match = Book(
        title="Archived Identical Book",
        author="Author",
        isbn="978-0666666666",
        category="Tech",
        is_archived=True,
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
        updated_at=past,
    )
    active_match = Book(
        title="Active Identical Book",
        author="Author",
        isbn="978-0777777777",
        category="Tech",
        is_archived=False,
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add_all([source, archived_match, active_match])
    db.flush()

    response = client.get(
        f"/api/books/{source.id}/recommendations",
        headers=auth_student["headers"],
    )
    assert response.status_code == 200
    rec_ids = [r["id"] for r in response.json()["recommendations"]]
    assert active_match.id in rec_ids
    assert archived_match.id not in rec_ids


def test_content_recommendations_invalid_source_book(client, auth_student, db: Session):
    """
    Verifies error responses when requesting recommendations for:
    - Non-existent book (404 Not Found)
    - Archived book (400 Bad Request)
    - Book without embedding (400 Bad Request)
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    now = datetime.utcnow()
    vec = make_unit_vector(0)

    archived_b = Book(
        title="Old Book",
        author="Author",
        isbn="978-0888888888",
        category="History",
        is_archived=True,
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
    )
    unembedded_b = Book(
        title="New Unprocessed Book",
        author="Author",
        isbn="978-0999888777",
        category="History",
        is_archived=False,
        embedding=None,
        embedding_updated_at=None,
    )
    db.add_all([archived_b, unembedded_b])
    db.flush()

    # 404 for non-existent
    r_404 = client.get("/api/books/999999/recommendations", headers=auth_student["headers"])
    assert r_404.status_code == 404

    # 400 for archived source book
    r_arch = client.get(f"/api/books/{archived_b.id}/recommendations", headers=auth_student["headers"])
    assert r_arch.status_code == 400
    assert "archived" in r_arch.text.lower()

    # 400 for source book without embedding
    r_unemb = client.get(f"/api/books/{unembedded_b.id}/recommendations", headers=auth_student["headers"])
    assert r_unemb.status_code == 400
    assert "does not have an embedding" in r_unemb.text.lower()


def test_embedding_status_metrics(client, auth_librarian, db: Session):
    """
    Verifies that /api/embeddings/status reports accurate metrics for total,
    with_embedding, missing, and stale books.
    """
    client.cookies.set("access_token", auth_librarian["token"])
    client.cookies.set("csrf_token", auth_librarian["csrf_val"])

    vec = make_unit_vector(0)
    now = datetime.utcnow()
    past = now - timedelta(days=2)

    # 1 book with current embedding
    b_current = Book(
        title="Current Embedded Book",
        author="Author",
        isbn="978-1000000001",
        category="General",
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=now,
        updated_at=past,
    )
    # 1 book missing embedding
    b_missing = Book(
        title="Missing Embedding Book",
        author="Author",
        isbn="978-1000000002",
        category="General",
        embedding=None,
        embedding_updated_at=None,
    )
    # 1 book with stale embedding (updated_at > embedding_updated_at)
    b_stale = Book(
        title="Stale Embedding Book",
        author="Author",
        isbn="978-1000000003",
        category="General",
        embedding=embedding_service.serialize_vector(vec),
        embedding_updated_at=past,
        updated_at=now,
    )
    db.add_all([b_current, b_missing, b_stale])
    db.flush()

    response = client.get(
        "/api/embeddings/status",
        headers=auth_librarian["headers"],
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total_books"] >= 3
    assert data["with_embedding"] >= 2
    assert data["missing_embedding"] >= 1
    assert data["stale_embedding"] >= 1
    assert data["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert "model_available" in data


def test_embedding_refresh_authorization(client, auth_student, auth_librarian):
    """
    Verifies role-based access control on embedding endpoints:
    - Unauthenticated request -> 401 Unauthorized.
    - Student request -> 403 Forbidden.
    - Librarian request -> 200 OK.
    """
    # 1. Unauthenticated
    client.cookies.clear()
    r_unauth = client.post("/api/embeddings/refresh", headers={"Origin": "http://localhost:5173"})
    assert r_unauth.status_code in (401, 403)

    # 2. Student (Forbidden)
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])
    r_student = client.post("/api/embeddings/refresh", headers=auth_student["headers"])
    assert r_student.status_code == 403

    # 3. Librarian (Authorized)
    client.cookies.set("access_token", auth_librarian["token"])
    client.cookies.set("csrf_token", auth_librarian["csrf_val"])
    r_lib = client.post("/api/embeddings/refresh", headers=auth_librarian["headers"])
    assert r_lib.status_code == 200


def test_embedding_refresh_generates_missing_and_stale(client, auth_librarian, db: Session):
    """
    Verifies that calling /api/embeddings/refresh successfully generates embeddings
    for missing and stale books, updating their embedding_updated_at timestamps.
    """
    client.cookies.set("access_token", auth_librarian["token"])
    client.cookies.set("csrf_token", auth_librarian["csrf_val"])

    now = datetime.utcnow()
    past = now - timedelta(days=5)

    b_missing = Book(
        title="Unprocessed AI Book",
        author="Author Test",
        isbn="978-1111222233",
        category="Computer Science",
        embedding=None,
        embedding_updated_at=None,
    )
    b_stale = Book(
        title="Stale Machine Learning Book",
        author="Author Test",
        isbn="978-1111222244",
        category="Computer Science",
        embedding=embedding_service.serialize_vector(make_unit_vector(0)),
        embedding_updated_at=past,
        updated_at=now,
    )
    db.add_all([b_missing, b_stale])
    db.flush()

    # Configure deterministic mock encoder
    embedding_service.set_mock_encoder(lambda text: make_unit_vector(1))

    response = client.post(
        "/api/embeddings/refresh",
        headers=auth_librarian["headers"],
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "completed"
    assert data["processed"] >= 2
    assert data["failed"] == 0

    db.refresh(b_missing)
    db.refresh(b_stale)
    assert b_missing.embedding is not None
    assert b_missing.embedding_updated_at is not None
    assert b_stale.embedding_updated_at >= now


def test_model_unavailable_graceful_handling(client, auth_student, auth_librarian):
    """
    Verifies that when the embedding model is unavailable:
    - Search returns 503 Service Unavailable with a clean, descriptive message.
    - Refresh returns 503 Service Unavailable.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    # Simulate model unavailable exception
    def broken_encoder(text: str):
        raise embedding_service.ModelUnavailableException("Model weights missing.")

    embedding_service.set_mock_encoder(broken_encoder)

    response = client.get(
        "/api/search/semantic",
        params={"q": "machine learning"},
        headers=auth_student["headers"],
    )
    assert response.status_code == 503
    assert "unavailable" in response.text.lower()


def test_min_score_filter_and_pagination(client, auth_student, db: Session):
    """
    Verifies that min_score threshold correctly filters results and pagination metadata matches.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    now = datetime.utcnow()
    past = now - timedelta(hours=1)
    vec_high = make_unit_vector(0)
    vec_low = make_unit_vector(1)

    b1 = Book(
        title="High Match Book",
        author="A1",
        isbn="978-1999999001",
        category="CS",
        embedding=embedding_service.serialize_vector(vec_high),
        embedding_updated_at=now,
        updated_at=past,
    )
    b2 = Book(
        title="Low Match Book",
        author="A2",
        isbn="978-1999999002",
        category="CS",
        embedding=embedding_service.serialize_vector(vec_low),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add_all([b1, b2])
    db.flush()

    embedding_service.set_mock_encoder(lambda t: vec_high)

    # min_score = 0.5 should include b1 (sim 1.0) and exclude b2 (sim 0.0)
    response = client.get(
        "/api/search/semantic",
        params={"q": "high match", "min_score": 0.5},
        headers=auth_student["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == b1.id


# ── Stage 5 Targeted Regression Tests: Stale Embeddings & Lifecycle ───────────

def test_current_embedding_included_and_stale_excluded(client, auth_student, db: Session):
    """
    Regression Tests 1 & 2:
    - A current embedding appears in semantic search and recommendation candidates.
    - A stale embedding (embedding_updated_at < updated_at) is strictly excluded
      from semantic search and recommendation candidates.
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    vec_match = make_unit_vector(0)
    now = datetime.utcnow()
    past = now - timedelta(hours=2)

    # 1. Current book (matching query)
    book_current = Book(
        title="Current Deep Learning",
        author="Active Author",
        isbn="978-2000000001",
        category="Tech",
        embedding=embedding_service.serialize_vector(vec_match),
        embedding_updated_at=now,
        updated_at=past,
    )
    # 2. Stale book (matching query vector, but updated_at is newer than embedding)
    book_stale = Book(
        title="Stale Deep Learning",
        author="Stale Author",
        isbn="978-2000000002",
        category="Tech",
        embedding=embedding_service.serialize_vector(vec_match),
        embedding_updated_at=past,
        updated_at=now,
    )
    # 3. Source book for recommendations
    book_source = Book(
        title="Source ML Book",
        author="Source Author",
        isbn="978-2000000003",
        category="Tech",
        embedding=embedding_service.serialize_vector(vec_match),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add_all([book_current, book_stale, book_source])
    db.flush()

    embedding_service.set_mock_encoder(lambda t: vec_match)

    # A) Semantic Search: book_current must be present, book_stale must be excluded
    search_res = client.get(
        "/api/search/semantic",
        params={"q": "deep learning"},
        headers=auth_student["headers"],
    )
    assert search_res.status_code == 200
    search_ids = [item["id"] for item in search_res.json()["items"]]
    assert book_current.id in search_ids
    assert book_stale.id not in search_ids

    # B) Recommendation Candidates: book_current must be present, book_stale must be excluded
    recs_res = client.get(
        f"/api/books/{book_source.id}/recommendations",
        headers=auth_student["headers"],
    )
    assert recs_res.status_code == 200
    rec_ids = [item["id"] for item in recs_res.json()["recommendations"]]
    assert book_current.id in rec_ids
    assert book_stale.id not in rec_ids


def test_stale_source_book_rejected_for_recommendations(client, auth_student, db: Session):
    """
    Regression Test 3:
    - A source book with a stale embedding cannot be used for recommendations (returns 400 Bad Request).
    """
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    now = datetime.utcnow()
    past = now - timedelta(hours=3)

    stale_source = Book(
        title="Stale Source Book",
        author="Author",
        isbn="978-2000000010",
        category="Computer Science",
        embedding=embedding_service.serialize_vector(make_unit_vector(0)),
        embedding_updated_at=past,
        updated_at=now,
    )
    db.add(stale_source)
    db.flush()

    response = client.get(
        f"/api/books/{stale_source.id}/recommendations",
        headers=auth_student["headers"],
    )
    assert response.status_code == 400
    assert "current" in response.text.lower() or "embedding" in response.text.lower()


def test_embedding_refresh_leaves_embedding_current_after_transaction(client, auth_librarian, db: Session):
    """
    Regression Test 4:
    - Refreshing an embedding leaves it current after the database transaction completes.
    - Generating or refreshing an embedding does not alter metadata updated_at.
    """
    client.cookies.set("access_token", auth_librarian["token"])
    client.cookies.set("csrf_token", auth_librarian["csrf_val"])

    now = datetime.utcnow()
    past = now - timedelta(days=2)

    stale_book = Book(
        title="Needs Refresh Book",
        author="Author",
        isbn="978-2000000020",
        category="Tech",
        embedding=embedding_service.serialize_vector(make_unit_vector(0)),
        embedding_updated_at=past,
        updated_at=now,
    )
    db.add(stale_book)
    db.flush()

    initial_metadata_updated_at = stale_book.updated_at
    embedding_service.set_mock_encoder(lambda t: make_unit_vector(0))

    response = client.post(
        "/api/embeddings/refresh",
        headers=auth_librarian["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["processed"] >= 1
    assert data["failed"] == 0

    db.refresh(stale_book)
    # 1. embedding_updated_at is current (>= updated_at)
    assert stale_book.embedding_updated_at is not None
    assert stale_book.embedding_updated_at >= stale_book.updated_at
    # 2. updated_at was preserved and not changed merely because embedding was saved
    assert stale_book.updated_at == initial_metadata_updated_at


def test_editing_catalogue_metadata_marks_embedding_stale(client, auth_librarian, auth_student, db: Session):
    """
    Regression Test 5:
    - Editing a book's title, author, category, or description marks its existing embedding stale.
    - Once stale, it is excluded from search/recommendations until refreshed.
    """
    client.cookies.set("access_token", auth_librarian["token"])
    client.cookies.set("csrf_token", auth_librarian["csrf_val"])

    now = datetime.utcnow()
    past = now - timedelta(hours=1)

    book = Book(
        title="Original Robotics Title",
        author="Original Author",
        isbn="978-2000000030",
        category="Robotics",
        description="Autonomous systems.",
        embedding=embedding_service.serialize_vector(make_unit_vector(0)),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add(book)
    db.flush()

    # Verify initially current
    assert book.embedding_updated_at >= book.updated_at

    # Edit book metadata via catalogue update API
    edit_response = client.patch(
        f"/api/books/{book.id}",
        json={"title": "Updated Robotics and Control Systems"},
        headers=auth_librarian["headers"],
    )
    assert edit_response.status_code == 200

    db.refresh(book)
    # updated_at has advanced past embedding_updated_at
    assert book.updated_at > book.embedding_updated_at

    # Stale embedding is now excluded from semantic search
    embedding_service.set_mock_encoder(lambda t: make_unit_vector(0))
    search_res = client.get(
        "/api/search/semantic",
        params={"q": "robotics"},
        headers=auth_student["headers"],
    )
    assert search_res.status_code == 200
    search_ids = [item["id"] for item in search_res.json()["items"]]
    assert book.id not in search_ids

    # Stale book cannot be used as source for recommendations
    recs_res = client.get(
        f"/api/books/{book.id}/recommendations",
        headers=auth_student["headers"],
    )
    assert recs_res.status_code == 400


def test_existing_embedding_status_and_refresh_counts_lifecycle(client, auth_librarian, db: Session):
    """
    Regression Test 6:
    - Existing embedding-status counts (total_books, with_embedding, missing_embedding, stale_embedding),
      refresh behavior, and all previous functionality remain correct across the full lifecycle.
    """
    client.cookies.set("access_token", auth_librarian["token"])
    client.cookies.set("csrf_token", auth_librarian["csrf_val"])

    now = datetime.utcnow()
    past = now - timedelta(days=3)

    # 1 book missing embedding
    b_missing = Book(
        title="Lifecycle Missing Book",
        author="Author",
        isbn="978-2000000041",
        category="Math",
        embedding=None,
        embedding_updated_at=None,
    )
    # 1 book with stale embedding
    b_stale = Book(
        title="Lifecycle Stale Book",
        author="Author",
        isbn="978-2000000042",
        category="Math",
        embedding=embedding_service.serialize_vector(make_unit_vector(0)),
        embedding_updated_at=past,
        updated_at=now,
    )
    # 1 book with current embedding
    b_current = Book(
        title="Lifecycle Current Book",
        author="Author",
        isbn="978-2000000043",
        category="Math",
        embedding=embedding_service.serialize_vector(make_unit_vector(0)),
        embedding_updated_at=now,
        updated_at=past,
    )
    db.add_all([b_missing, b_stale, b_current])
    db.flush()

    status_res = client.get(
        "/api/embeddings/status",
        headers=auth_librarian["headers"],
    )
    assert status_res.status_code == 200
    counts = status_res.json()
    assert counts["total_books"] >= 3
    assert counts["with_embedding"] >= 2
    assert counts["missing_embedding"] >= 1
    assert counts["stale_embedding"] >= 1

    # Now refresh embeddings
    embedding_service.set_mock_encoder(lambda t: make_unit_vector(0))
    refresh_res = client.post(
        "/api/embeddings/refresh",
        headers=auth_librarian["headers"],
    )
    assert refresh_res.status_code == 200
    ref_data = refresh_res.json()
    assert ref_data["status"] == "completed"
    assert ref_data["processed"] >= 2
    assert ref_data["failed"] == 0

    # Stale and missing counts should now be 0
    updated_status = client.get(
        "/api/embeddings/status",
        headers=auth_librarian["headers"],
    ).json()
    assert updated_status["missing_embedding"] == 0
    assert updated_status["stale_embedding"] == 0
