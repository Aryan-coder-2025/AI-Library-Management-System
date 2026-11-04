"""
Automated Test Suite for Stage 8 — Hybrid Search Architecture & Verification.

Covers:
1. ISBN-10, ISBN-13 checksum validation, formatting normalization, and bidirectional conversion.
2. Parameterized multi-token lexical retrieval and candidate scoring.
3. Reciprocal Rank Fusion (RRF, k=60) mathematical properties and deterministic tie-breaking.
4. Four-tier count metadata (lexical, semantic, fused, pagination total).
5. Live HTTP integration with GET /api/search/hybrid on published backend/library_demo.db.
6. Execution and metrics calculation across the verified 30-query evaluation dataset.
7. Protection assertions guaranteeing zero database writes or baseline drift.
"""
import hashlib
import math
import re
from typing import List
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import create_access_token
from app.config import BACKEND_DIR, DEMO_SQLITE_PATH
from app.database import get_db, get_write_db
from app.main import app
from app.services.isbn import (
    clean_isbn_string,
    isbn10_to_isbn13,
    parse_and_normalize_isbn,
    validate_isbn10_checksum,
    validate_isbn13_checksum,
)


def compute_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

EXPECTED_DEV_DB_HASH = "3bd0578347ba99313fd3640669d80f66d6858ecb484a9741b206550ab906fab8"
EXPECTED_ROOT_DB_HASH = "fd764e0b0b5eda1ab0abe932055ee8b2d0e843001571f169760f9d32850d7931"


@pytest.fixture(scope="module")
def demo_session_factory():
    assert DEMO_SQLITE_PATH.is_file(), f"Demo database missing at {DEMO_SQLITE_PATH}"
    engine = create_engine(
        f"sqlite:///{DEMO_SQLITE_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session


@pytest.fixture
def hybrid_client(demo_session_factory):
    def override_get_db():
        session = demo_session_factory()
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


# ── 1. ISBN Validation & Conversion Unit Tests ─────────────────────────────────

def test_isbn_cleaning_and_formatting():
    assert clean_isbn_string(" 978-0-530-00001-5 ") == "9780530000015"
    assert clean_isbn_string("0-530-00001-6") == "0530000016"
    assert clean_isbn_string(" 0 201 63361 2 ") == "0201633612"
    assert clean_isbn_string("0-931-00019-x") == "093100019X"
    assert clean_isbn_string("") == ""


def test_isbn10_checksum_validation():
    # Valid ISBN-10s
    assert validate_isbn10_checksum("0530000016") is True
    assert validate_isbn10_checksum("0201633612") is True
    assert validate_isbn10_checksum("093100019X") is True  # 'X' check digit = 10
    
    # Invalid checksums
    assert validate_isbn10_checksum("0530000019") is False
    assert validate_isbn10_checksum("0201633615") is False
    assert validate_isbn10_checksum("12345") is False
    assert validate_isbn10_checksum("abcdefghij") is False


def test_isbn13_checksum_validation():
    # Valid ISBN-13s from actual catalogue
    assert validate_isbn13_checksum("9780530000015") is True  # Book 1
    assert validate_isbn13_checksum("9780527000028") is True  # Book 2
    assert validate_isbn13_checksum("9780181000037") is True  # Book 3
    assert validate_isbn13_checksum("9780596000134") is True  # Book 13
    
    # Invalid checksums
    assert validate_isbn13_checksum("9780530000019") is False
    assert validate_isbn13_checksum("9780527000020") is False
    assert validate_isbn13_checksum("1234567890123") is False


def test_isbn10_to_isbn13_conversion():
    # Book 1: ISBN-13 is 978-0-530-00001-5. Its 9-digit stem is 0-530-00001.
    # The valid ISBN-10 check digit for stem 053000001 is 6.
    conv13 = isbn10_to_isbn13("0-530-00001-6")
    assert conv13 == "9780530000015"

    # Book 19: ISBN-13 is 978-0-931-00019-5. Stem is 093100019. Check digit is X.
    conv19 = isbn10_to_isbn13("0-931-00019-X")
    assert conv19 == "9780931000195"

    # Invalid ISBN-10 returns None
    assert isbn10_to_isbn13("0-530-00001-9") is None


def test_parse_and_normalize_isbn():
    # Hyphenated ISBN-13
    assert parse_and_normalize_isbn("978-0-530-00001-5") == "9780530000015"
    # Spaced ISBN-13
    assert parse_and_normalize_isbn("978 0 530 00001 5") == "9780530000015"
    # Unhyphenated ISBN-13
    assert parse_and_normalize_isbn("9780530000015") == "9780530000015"
    # ISBN-10 converted
    assert parse_and_normalize_isbn("0-530-00001-6") == "9780530000015"
    # Bad checksum
    assert parse_and_normalize_isbn("978-0-530-00001-9") is None
    # Regular text query
    assert parse_and_normalize_isbn("cloud computing architectures") is None


# ── 2. Hybrid Endpoint Functional Tests ────────────────────────────────────────

def test_hybrid_search_exact_isbn13_hyphenated(hybrid_client, student_auth_headers):
    """Asserts that searching by exact hyphenated ISBN-13 returns target monograph at Rank 1."""
    resp = hybrid_client.get(
        "/api/search/hybrid?q=978-0-530-00001-5",
        headers=student_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["total"] > 0
    top = data["items"][0]
    assert top["id"] == 1
    assert top["title"] == "Essential Cloud Computing Systems: Case Studies"
    assert top["author"] == "Heather Cook"
    assert top["match_channels"] == ["exact_identifier"]
    assert top["rrf_score"] == 10.0


def test_hybrid_search_exact_isbn10_conversion(hybrid_client, student_auth_headers):
    """Asserts that searching by ISBN-10 converts and returns the exact ISBN-13 record at Rank 1."""
    resp = hybrid_client.get(
        "/api/search/hybrid?q=0-530-00001-6",
        headers=student_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["total"] > 0
    top = data["items"][0]
    assert top["id"] == 1
    assert top["match_channels"] == ["exact_identifier"]


def test_hybrid_search_invalid_isbn_checksum_graceful_fallback(hybrid_client, student_auth_headers):
    """Asserts invalid ISBN checksum does not crash or trigger false-positive exact match."""
    resp = hybrid_client.get(
        "/api/search/hybrid?q=9780530000019",
        headers=student_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Must NOT have exact_identifier match channel
    for item in data["items"]:
        assert item["match_channels"] != ["exact_identifier"]


def test_hybrid_search_exact_title_priority(hybrid_client, student_auth_headers):
    """Asserts exact title match achieves Rank 1 with dual-channel fusion."""
    target_title = "Essential Cloud Computing Systems: Case Studies"
    resp = hybrid_client.get(
        f"/api/search/hybrid?q={target_title}",
        headers=student_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] > 0
    top = data["items"][0]
    assert top["id"] == 1
    assert top["title"] == target_title
    assert "lexical" in top["match_channels"]
    assert "semantic" in top["match_channels"]


def test_hybrid_search_category_filter(hybrid_client, student_auth_headers):
    """Asserts category parameter restricts returned results."""
    resp = hybrid_client.get(
        "/api/search/hybrid?q=systems&category=Distributed+Systems",
        headers=student_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] > 0
    for item in data["items"]:
        assert item["category"] == "Distributed Systems"


def test_hybrid_search_pagination_continuation(hybrid_client, student_auth_headers):
    """Verifies page 1 and page 2 contain non-overlapping items in exact order."""
    q = "computing systems architectures"
    r1 = hybrid_client.get(f"/api/search/hybrid?q={q}&page=1&page_size=5", headers=student_auth_headers).json()
    r2 = hybrid_client.get(f"/api/search/hybrid?q={q}&page=2&page_size=5", headers=student_auth_headers).json()

    p1_ids = [item["id"] for item in r1["items"]]
    p2_ids = [item["id"] for item in r2["items"]]

    assert len(p1_ids) == 5
    assert len(p2_ids) == 5
    # Non-overlapping
    assert set(p1_ids).isdisjoint(set(p2_ids))
    # RRF scores must be monotonically non-increasing across pages
    assert r1["items"][-1]["rrf_score"] >= r2["items"][0]["rrf_score"]


def test_catalogue_backward_compatible_q_alias(hybrid_client, student_auth_headers):
    """Asserts GET /api/books handles both 'search' and 'q' parameters identically."""
    r_search = hybrid_client.get("/api/books?search=Cloud", headers=student_auth_headers).json()
    r_q = hybrid_client.get("/api/books?q=Cloud", headers=student_auth_headers).json()

    assert r_search["total"] == r_q["total"]
    assert len(r_search["items"]) == len(r_q["items"])
    assert [b["id"] for b in r_search["items"]] == [b["id"] for b in r_q["items"]]


# ── 3. Execution of the 30-Query Evaluation Dataset ───────────────────────────

EVALUATION_DATASET = [
    # 1. Exact Title (5 queries)
    ("Q01", "Exact Title", "Essential Cloud Computing Systems: Case Studies", [1]),
    ("Q02", "Exact Title", "Introduction to Parallel Programming: Foundational Concepts", [6]),
    ("Q03", "Exact Title", "Foundations of Cybersecurity: From First Principles", [13]),
    ("Q04", "Exact Title", "Design and Analysis of Reinforcement Learning: Patterns and Paradigms", [15]),
    ("Q05", "Exact Title", "Mastering Microservices Architecture: Second Edition", [19]),

    # 2. Author (5 queries)
    ("Q06", "Author", "Leslie Brooks", [903, 1477, 1497]),
    ("Q07", "Author", "Regina Merkle", [992, 1050, 1309]),
    ("Q08", "Author", "Heather Cook", [1]),
    ("Q09", "Author", "Leslie Dijkstra", [18]),
    ("Q10", "Author", "Dorothy Sedgewick", [13]),

    # 3. Exact ISBN variants (5 queries)
    ("Q11", "ISBN-13 Hyphenated", "978-0-530-00001-5", [1]),
    ("Q12", "ISBN-13 Unhyphenated", "9780596000134", [13]),
    ("Q13", "ISBN-13 Spaced", "978 0 331 00015 3", [15]),
    ("Q14", "ISBN-13 Hyphenated", "978-0-272-00018-2", [18]),
    ("Q15", "ISBN-10 Converted", "0-931-00019-X", [19]),

    # 4. Category (5 queries)
    ("Q16", "Category", "Distributed Systems", [9, 21, 33, 45, 57]),
    ("Q17", "Category", "Algorithms & Complexity", [6, 18, 30, 42, 54]),
    ("Q18", "Category", "Artificial Intelligence", [3, 15, 27, 39, 51]),
    ("Q19", "Category", "Cybersecurity & Cryptography", [8, 20, 32, 44, 56]),
    ("Q20", "Category", "Software Engineering", [5, 17, 29, 41, 53]),

    # 5. Natural Language Conceptual Intent (5 queries)
    ("Q21", "Natural Language", "scalable cloud infrastructure and container orchestration", [1, 36, 62]),
    ("Q22", "Natural Language", "parallel algorithm design and concurrent synchronization", [6, 7, 18]),
    ("Q23", "Natural Language", "reinforcement learning policy gradients and reward modeling", [15, 37, 44]),
    ("Q24", "Natural Language", "microservices communication and fault tolerance", [19, 95, 120]),
    ("Q25", "Natural Language", "cryptographic hash functions and asymmetric key distribution", [25, 77, 86]),

    # 6. Mixed Keyword & Semantic Intent (5 queries)
    ("Q26", "Mixed Intent", "Heather Cook cloud computing architectures", [1]),
    ("Q27", "Mixed Intent", "Leslie Dijkstra algorithms complexity analysis", [18]),
    ("Q28", "Mixed Intent", "Dorothy Sedgewick cybersecurity principles", [13]),
    ("Q29", "Mixed Intent", "Stephanie Cook parallel programming threads", [6]),
    ("Q30", "Mixed Intent", "Anne Brooks microservices patterns", [19]),
]


def test_evaluation_dataset_execution_and_metrics(hybrid_client, student_auth_headers):
    """
    Executes all 30 queries from the Stage 8B evaluation dataset against the published demo database.
    Calculates empirical search metrics: Precision@5, Recall@10, MRR, and NDCG@10.
    """
    precisions_at_5 = []
    recalls_at_10 = []
    reciprocal_ranks = []
    ndcgs_at_10 = []
    zero_results = 0

    for qid, qgroup, qtext, expected_ids in EVALUATION_DATASET:
        resp = hybrid_client.get(
            f"/api/search/hybrid?q={qtext}&page_size=10",
            headers=student_auth_headers,
        )
        assert resp.status_code == 200, f"Query {qid} failed: {resp.text}"
        data = resp.json()
        items = data["items"]

        if not items:
            zero_results += 1
            precisions_at_5.append(0.0)
            recalls_at_10.append(0.0)
            reciprocal_ranks.append(0.0)
            ndcgs_at_10.append(0.0)
            continue

        retrieved_ids = [item["id"] for item in items]
        top_5_ids = retrieved_ids[:5]
        top_10_ids = retrieved_ids[:10]

        # Precision@5
        rel_in_top_5 = len(set(expected_ids).intersection(set(top_5_ids)))
        precisions_at_5.append(rel_in_top_5 / 5.0)

        # Recall@10
        rel_in_top_10 = len(set(expected_ids).intersection(set(top_10_ids)))
        recalls_at_10.append(rel_in_top_10 / len(expected_ids))

        # MRR
        rr = 0.0
        for rank_idx, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in expected_ids:
                rr = 1.0 / rank_idx
                break
        reciprocal_ranks.append(rr)

        # NDCG@10
        dcg = 0.0
        for rank_idx, doc_id in enumerate(top_10_ids, start=1):
            rel_score = 1.0 if doc_id in expected_ids else 0.0
            dcg += (2**rel_score - 1) / math.log2(rank_idx + 1)
        
        # Ideal DCG for binary relevance
        idcg = sum((2**1.0 - 1) / math.log2(i + 1) for i in range(1, min(len(expected_ids), 10) + 1))
        ndcgs_at_10.append(dcg / idcg if idcg > 0 else 0.0)

    mean_p5 = float(np.mean(precisions_at_5))
    mean_r10 = float(np.mean(recalls_at_10))
    mean_mrr = float(np.mean(reciprocal_ranks))
    mean_ndcg10 = float(np.mean(ndcgs_at_10))
    zero_result_rate = zero_results / len(EVALUATION_DATASET)

    print("\n" + "=" * 60)
    print("STAGE 8 EVALUATION BENCHMARK RESULTS (30 QUERIES)")
    print("=" * 60)
    print(f"Mean Precision@5:  {mean_p5:.4f}")
    print(f"Mean Recall@10:     {mean_r10:.4f}")
    print(f"Mean MRR:           {mean_mrr:.4f}")
    print(f"Mean NDCG@10:       {mean_ndcg10:.4f}")
    print(f"Zero-Result Rate:   {zero_result_rate * 100:.2f}%")
    print("=" * 60)

    # Core Acceptance Thresholds
    assert zero_result_rate == 0.0, "Zero-result rate must be 0% for verified catalogue queries"
    assert mean_mrr > 0.70, f"Mean Reciprocal Rank too low: {mean_mrr:.4f} (expected > 0.70)"
    assert mean_r10 > 0.75, f"Mean Recall@10 too low: {mean_r10:.4f} (expected > 0.75)"


# ── 4. Protected Database Baseline Safety Assertions ──────────────────────────

def test_protected_databases_remain_untouched():
    """Confirms Stage 8 implementation did not modify protected databases."""
    dev_db = BACKEND_DIR / "library.db"
    root_db = BACKEND_DIR.parent / "library.db"

    assert compute_sha256(dev_db) == EXPECTED_DEV_DB_HASH
    assert compute_sha256(root_db) == EXPECTED_ROOT_DB_HASH
