"""
Automated Test Suite for Stage 12.11 — Academic Research Discovery & Book Waitlists (CIRC-02).

Validates:
1. OpenAlex, arXiv, and Crossref adapters (mocked HTTP responses, timeouts, JATS stripping, inverted index reconstruction).
2. Federated research aggregator: multi-provider search, cross-provider deduplication, and partial failure isolation.
3. Book hold placement: eligibility, shelf availability check, duplicate rejection, and FIFO queue position.
4. Circulation integration: copy allocation upon return, hold-ready notification, loan issuance hold fulfillment, and unauthorized borrower blocking.
5. Hold cancellation: automatic copy reallocation to next waiting patron.
6. Hold expiration: sweep transitions uncollected holds to expired and advances queue.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.database import atomic_write
from app.models import Book, BookCopy, BookHold, Loan, Notification, User
from app.services.research.aggregator import AcademicResearchService, normalize_title_key
from app.services.research.arxiv import ArxivAdapter
from app.services.research.crossref import CrossrefAdapter, clean_jats_abstract
from app.services.research.openalex import OpenAlexAdapter, reconstruct_inverted_index


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def patron_student_1(db: Session) -> User:
    with atomic_write(db):
        user = User(
            email="patron.one@university.edu",
            username="patron_one",
            full_name="Patron Student One",
            hashed_password=hash_password("ValidPassword123!"),
            role="student",
            is_active=True,
        )
        db.add(user)
    return user


@pytest.fixture
def patron_student_2(db: Session) -> User:
    with atomic_write(db):
        user = User(
            email="patron.two@university.edu",
            username="patron_two",
            full_name="Patron Student Two",
            hashed_password=hash_password("ValidPassword123!"),
            role="student",
            is_active=True,
        )
        db.add(user)
    return user


@pytest.fixture
def patron_student_3(db: Session) -> User:
    with atomic_write(db):
        user = User(
            email="patron.three@university.edu",
            username="patron_three",
            full_name="Patron Student Three",
            hashed_password=hash_password("ValidPassword123!"),
            role="student",
            is_active=True,
        )
        db.add(user)
    return user


@pytest.fixture
def librarian_user(db: Session) -> User:
    with atomic_write(db):
        user = User(
            email="circ.librarian@university.edu",
            username="circ_librarian",
            full_name="Circulation Librarian",
            hashed_password=hash_password("ValidPassword123!"),
            role="librarian",
            is_active=True,
        )
        db.add(user)
    return user


@pytest.fixture
def sample_monograph(db: Session) -> Book:
    with atomic_write(db):
        book = Book(
            title="Introduction to Modern Quantum Algorithms",
            author="Dr. Alan V. Turing",
            isbn="9780123456789",
            category="Quantum Computing",
            description="Comprehensive guide to quantum algorithms.",
            is_archived=False,
        )
        db.add(book)
    return book


def make_auth_headers(client: TestClient, user_id: int, role: str) -> dict:
    token = create_access_token(user_id=user_id, role=role)
    csrf_val = f"csrf-token-{user_id}"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": csrf_val,
        "Authorization": f"Bearer {token}",
    }


# ── 1. Academic Research Provider Adapters (Mocked) ──────────────────────────

def test_reconstruct_inverted_index():
    index = {
        "Quantum": [0],
        "computing": [1],
        "is": [2],
        "powerful": [3],
    }
    assert reconstruct_inverted_index(index) == "Quantum computing is powerful"
    assert reconstruct_inverted_index(None) is None
    assert reconstruct_inverted_index({}) is None


def test_clean_jats_abstract():
    raw = "<jats:p>This study evaluates <jats:italic>deep learning</jats:italic> models.</jats:p>"
    assert clean_jats_abstract(raw) == "This study evaluates deep learning models."
    assert clean_jats_abstract(None) is None


def test_openalex_adapter_success():
    adapter = OpenAlexAdapter()
    mock_payload = {
        "results": [
            {
                "id": "https://openalex.org/W12345",
                "title": "Quantum Circuit Optimization",
                "authorships": [{"author": {"display_name": "Alice Quantum"}}],
                "abstract_inverted_index": {"Circuit": [0], "optimization": [1]},
                "publication_year": 2023,
                "doi": "https://doi.org/10.1000/12345",
                "primary_location": {"source": {"display_name": "IEEE Transactions"}},
                "open_access": {"is_oa": True},
                "cited_by_count": 42,
            }
        ]
    }

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        results = adapter.search("Quantum", limit=5)
        assert len(results) == 1
        paper = results[0]
        assert paper.title == "Quantum Circuit Optimization"
        assert paper.authors == ["Alice Quantum"]
        assert paper.abstract == "Circuit optimization"
        assert paper.publication_year == 2023
        assert paper.doi == "https://doi.org/10.1000/12345"
        assert paper.venue == "IEEE Transactions"
        assert paper.open_access is True
        assert paper.citation_count == 42
        assert paper.source_provider == "openalex"


def test_openalex_adapter_timeout_graceful():
    adapter = OpenAlexAdapter()
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Timeout")):
        results = adapter.search("Quantum")
        assert results == []


def test_arxiv_adapter_success():
    adapter = ArxivAdapter()
    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2301.00001v1</id>
        <title>Foundations of Neural Information Processing</title>
        <summary>A foundational overview of neural networks.</summary>
        <published>2023-01-01T00:00:00Z</published>
        <author><name>Bob Scholar</name></author>
        <arxiv:doi>10.48550/arXiv.2301.00001</arxiv:doi>
      </entry>
    </feed>
    """

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_xml
        mock_get.return_value = mock_resp

        results = adapter.search("Neural", limit=5)
        assert len(results) == 1
        paper = results[0]
        assert paper.title == "Foundations of Neural Information Processing"
        assert paper.authors == ["Bob Scholar"]
        assert paper.abstract == "A foundational overview of neural networks."
        assert paper.publication_year == 2023
        assert paper.arxiv_id == "2301.00001v1"
        assert paper.open_access is True
        assert paper.source_provider == "arxiv"


def test_crossref_adapter_success():
    adapter = CrossrefAdapter()
    mock_payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1016/j.jcp.2023.01",
                    "title": ["Computational Fluid Dynamics at Scale"],
                    "author": [{"given": "Carol", "family": "Scientist"}],
                    "published-print": {"date-parts": [[2023, 5]]},
                    "container-title": ["Journal of Computational Physics"],
                    "abstract": "<jats:p>Large-scale numerical simulations.</jats:p>",
                    "is-referenced-by-count": 18,
                    "URL": "https://doi.org/10.1016/j.jcp.2023.01",
                }
            ]
        }
    }

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        results = adapter.search("Fluid Dynamics", limit=5)
        assert len(results) == 1
        paper = results[0]
        assert paper.title == "Computational Fluid Dynamics at Scale"
        assert paper.authors == ["Carol Scientist"]
        assert paper.abstract == "Large-scale numerical simulations."
        assert paper.publication_year == 2023
        assert paper.doi == "10.1016/j.jcp.2023.01"
        assert paper.venue == "Journal of Computational Physics"
        assert paper.source_provider == "crossref"


def test_aggregator_deduplication_and_partial_failure():
    service = AcademicResearchService()

    # Provider 1 (OpenAlex) returns paper A with DOI
    # Provider 2 (Crossref) returns paper A with same DOI (duplicate)
    # Provider 3 (arXiv) raises timeout exception (partial failure)
    from app.schemas import AcademicPaperResult

    paper_openalex = AcademicPaperResult(
        id="openalex:1",
        title="Attention Is All You Need",
        authors=["Vaswani et al."],
        doi="10.5555/attention",
        source_provider="openalex",
        open_access=True,
    )
    paper_crossref_dup = AcademicPaperResult(
        id="crossref:1",
        title="Attention Is All You Need",
        authors=["A. Vaswani"],
        doi="10.5555/attention",  # Same DOI
        source_provider="crossref",
        open_access=False,
    )

    with patch.object(service.providers["openalex"], "search", return_value=[paper_openalex]), \
         patch.object(service.providers["crossref"], "search", return_value=[paper_crossref_dup]), \
         patch.object(service.providers["arxiv"], "search", side_effect=Exception("Connection reset")):

        response = service.search_papers(query="Attention Is All You Need", use_cache=False)

        # Partial failure handled gracefully: OpenAlex and Crossref active, arXiv absent
        assert "openalex" in response.active_providers
        assert "crossref" in response.active_providers
        assert "arxiv" not in response.active_providers

        # Deduplicated: only 1 instance returned instead of 2
        assert len(response.results) == 1
        assert response.results[0].doi == "10.5555/attention"


def test_research_search_api_endpoint(client: TestClient):
    with patch("app.services.research.aggregator.academic_research_service.search_papers") as mock_search:
        from app.schemas import AcademicSearchResponse
        mock_search.return_value = AcademicSearchResponse(
            query="test",
            total_results=0,
            page=1,
            page_size=15,
            providers_queried=["openalex"],
            active_providers=["openalex"],
            results=[],
        )

        resp = client.get("/api/research/search?q=test&providers=openalex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test"
        assert "providers_queried" in data


def test_research_providers_endpoint(client: TestClient):
    resp = client.get("/api/research/providers")
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert len(providers) == 3
    ids = {p["id"] for p in providers}
    assert ids == {"openalex", "arxiv", "crossref"}


# ── 2. Book Waitlists & Holds Lifecycle (CIRC-02) ───────────────────────────

def test_place_hold_rejected_when_copies_available_on_shelf(
    client: TestClient,
    patron_student_1: User,
    sample_monograph: Book,
    db: Session,
):
    # Add an available copy to the shelf
    with atomic_write(db):
        copy = BookCopy(
            book_id=sample_monograph.id,
            copy_code="QUANTUM-001",
            operational_status="available",
        )
        db.add(copy)

    headers = make_auth_headers(client, patron_student_1.id, "student")
    resp = client.post(
        "/api/holds",
        json={"book_id": sample_monograph.id},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "available on library shelves" in resp.json()["detail"].lower()


def test_place_hold_success_when_all_copies_on_loan(
    client: TestClient,
    patron_student_1: User,
    patron_student_2: User,
    librarian_user: User,
    sample_monograph: Book,
    db: Session,
):
    # Monograph has 1 copy, currently on loan to student 2
    with atomic_write(db):
        copy = BookCopy(
            book_id=sample_monograph.id,
            copy_code="QUANTUM-002",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        loan = Loan(
            student_id=patron_student_2.id,
            copy_id=copy.id,
            issued_by_id=librarian_user.id,
            issued_at=datetime.utcnow() - timedelta(days=2),
            due_date=(datetime.utcnow() + timedelta(days=12)).date(),
        )
        db.add(loan)

    # Student 1 places a hold
    headers = make_auth_headers(client, patron_student_1.id, "student")
    resp = client.post(
        "/api/holds",
        json={"book_id": sample_monograph.id},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "waiting"
    assert data["queue_position"] == 1
    assert data["copy_id"] is None


def test_duplicate_hold_rejected(
    client: TestClient,
    patron_student_1: User,
    sample_monograph: Book,
    db: Session,
):
    # Student 1 already has a waiting hold
    with atomic_write(db):
        hold = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_1.id,
            status="waiting",
            created_at=datetime.utcnow(),
        )
        db.add(hold)

    headers = make_auth_headers(client, patron_student_1.id, "student")
    resp = client.post(
        "/api/holds",
        json={"book_id": sample_monograph.id},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "already have an active hold" in resp.json()["detail"].lower()


def test_fifo_queue_ordering_and_return_copy_allocation(
    client: TestClient,
    patron_student_1: User,
    patron_student_2: User,
    librarian_user: User,
    sample_monograph: Book,
    db: Session,
):
    with atomic_write(db):
        copy = BookCopy(
            book_id=sample_monograph.id,
            copy_code="QUANTUM-003",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        # Existing loan on this copy
        loan = Loan(
            student_id=librarian_user.id,
            copy_id=copy.id,
            issued_by_id=librarian_user.id,
            issued_at=datetime.utcnow() - timedelta(days=5),
            due_date=(datetime.utcnow() + timedelta(days=9)).date(),
        )
        db.add(loan)
        db.flush()

        # Student 1 placed hold first
        hold1 = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_1.id,
            status="waiting",
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        # Student 2 placed hold second
        hold2 = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_2.id,
            status="waiting",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.add(hold1)
        db.add(hold2)

    # 1. Return the loan via return endpoint
    lib_headers = make_auth_headers(client, librarian_user.id, "librarian")
    resp_ret = client.post(
        f"/api/loans/{loan.id}/return",
        headers=lib_headers,
    )
    assert resp_ret.status_code == 200

    # 2. Verify FIFO queue allocation:
    # hold1 (first in line) is now 'ready_for_pickup' with the copy allocated!
    # hold2 remains 'waiting' in position 1.
    db.refresh(hold1)
    db.refresh(hold2)

    assert hold1.status == "ready_for_pickup"
    assert hold1.copy_id == copy.id
    assert hold1.allocated_at is not None
    assert hold1.pickup_expires_at is not None

    assert hold2.status == "waiting"
    assert hold2.copy_id == None

    # Verify notification created for student 1
    notif = db.execute(
        select(Notification).where(
            Notification.user_id == patron_student_1.id,
            Notification.notification_type == "hold_ready",
        )
    ).scalar_one_or_none()
    assert notif is not None
    assert "ready for pickup" in notif.title.lower()


def test_loan_issue_blocks_unauthorized_borrower_when_held(
    client: TestClient,
    patron_student_1: User,
    patron_student_2: User,
    librarian_user: User,
    sample_monograph: Book,
    db: Session,
):
    with atomic_write(db):
        copy = BookCopy(
            book_id=sample_monograph.id,
            copy_code="QUANTUM-004",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        # Copy is allocated to Student 1 awaiting pickup
        hold = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_1.id,
            copy_id=copy.id,
            status="ready_for_pickup",
            created_at=datetime.utcnow(),
            allocated_at=datetime.utcnow(),
            pickup_expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.add(hold)

    lib_headers = make_auth_headers(client, librarian_user.id, "librarian")

    # Attempt to issue copy to Student 2 (NOT the hold owner)
    resp_fail = client.post(
        "/api/loans",
        json={"student_id": patron_student_2.id, "copy_id": copy.id},
        headers=lib_headers,
    )
    assert resp_fail.status_code == 400
    assert "reserved on hold" in resp_fail.json()["detail"].lower()

    # Issue copy to Student 1 (the legitimate hold owner) -> SUCCEEDS & fulfills hold!
    resp_success = client.post(
        "/api/loans",
        json={"student_id": patron_student_1.id, "copy_id": copy.id},
        headers=lib_headers,
    )
    assert resp_success.status_code == 201

    db.refresh(hold)
    assert hold.status == "fulfilled"
    assert hold.fulfilled_at is not None


def test_cancel_hold_reallocates_copy_to_next_in_queue(
    client: TestClient,
    patron_student_1: User,
    patron_student_2: User,
    sample_monograph: Book,
    db: Session,
):
    with atomic_write(db):
        copy = BookCopy(
            book_id=sample_monograph.id,
            copy_code="QUANTUM-005",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        # Student 1 has ready_for_pickup hold
        hold1 = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_1.id,
            copy_id=copy.id,
            status="ready_for_pickup",
            created_at=datetime.utcnow() - timedelta(days=1),
            allocated_at=datetime.utcnow() - timedelta(days=1),
            pickup_expires_at=datetime.utcnow() + timedelta(days=6),
        )
        # Student 2 is waiting
        hold2 = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_2.id,
            copy_id=None,
            status="waiting",
            created_at=datetime.utcnow(),
        )
        db.add(hold1)
        db.add(hold2)

    # Student 1 cancels their hold
    headers1 = make_auth_headers(client, patron_student_1.id, "student")
    resp_cancel = client.post(
        f"/api/holds/{hold1.id}/cancel",
        headers=headers1,
    )
    assert resp_cancel.status_code == 200

    db.refresh(hold1)
    db.refresh(hold2)

    assert hold1.status == "cancelled"

    # Released copy was immediately reallocated to Student 2!
    assert hold2.status == "ready_for_pickup"
    assert hold2.copy_id == copy.id


def test_sweep_expired_holds_advances_queue(
    client: TestClient,
    patron_student_1: User,
    patron_student_2: User,
    librarian_user: User,
    sample_monograph: Book,
    db: Session,
):
    with atomic_write(db):
        copy = BookCopy(
            book_id=sample_monograph.id,
            copy_code="QUANTUM-006",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        # Hold 1 expired yesterday
        hold1 = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_1.id,
            copy_id=copy.id,
            status="ready_for_pickup",
            created_at=datetime.utcnow() - timedelta(days=8),
            allocated_at=datetime.utcnow() - timedelta(days=8),
            pickup_expires_at=datetime.utcnow() - timedelta(days=1),  # Expired
        )
        # Hold 2 waiting
        hold2 = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_2.id,
            copy_id=None,
            status="waiting",
            created_at=datetime.utcnow() - timedelta(days=5),
        )
        db.add(hold1)
        db.add(hold2)

    lib_headers = make_auth_headers(client, librarian_user.id, "librarian")
    resp = client.post(
        "/api/holds/sweep",
        headers=lib_headers,
    )
    assert resp.status_code == 200
    assert "1 expired holds" in resp.json()["message"]

    db.refresh(hold1)
    db.refresh(hold2)

    assert hold1.status == "expired"
    assert hold2.status == "ready_for_pickup"
    assert hold2.copy_id == copy.id


def test_patron_view_my_holds(
    client: TestClient,
    patron_student_1: User,
    sample_monograph: Book,
    db: Session,
):
    with atomic_write(db):
        hold = BookHold(
            book_id=sample_monograph.id,
            user_id=patron_student_1.id,
            status="waiting",
            created_at=datetime.utcnow(),
        )
        db.add(hold)

    headers = make_auth_headers(client, patron_student_1.id, "student")
    resp = client.get(
        "/api/holds/me",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["book_title"] == sample_monograph.title
    assert data["items"][0]["queue_position"] == 1


def test_conversational_scholarly_query_cleaning():
    from app.services.research.aggregator import clean_scholarly_query

    assert clean_scholarly_query("ok can you tell me about some famous research papers on nanorobotics") == "nanorobotics"
    assert clean_scholarly_query("please find me research papers on quantum computing") == "quantum computing"
    assert clean_scholarly_query("what are the best articles on CRISPR gene editing?") == "CRISPR gene editing"
    assert clean_scholarly_query("papers about distributed consensus") == "distributed consensus"
    assert clean_scholarly_query("Attention Is All You Need") == "Attention Is All You Need"

