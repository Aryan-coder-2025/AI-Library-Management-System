"""
Test suite for physical ISBN lookup and automated copy-cataloging endpoints.
Verifies bibliographic query parsing, database conflict checks, and atomic accession barcode generation.
"""
import pytest
from sqlalchemy.orm import Session
from app.models import User, Book, BookCopy
from app.auth import create_access_token, hash_password
from app.database import atomic_write


@pytest.fixture
def auth_librarian(client, db: Session):
    with atomic_write(db):
        user = User(
            email="isbn_librarian@library.org",
            full_name="ISBN Cataloging Specialist",
            hashed_password=hash_password("SpecialistPass123!"),
            role="librarian",
            is_active=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id

    token = create_access_token(user_id=user_id, role="librarian")
    csrf_val = "isbn-csrf-token-val"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user_id": user_id,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


def test_isbn_lookup_known_academic_book(client, auth_librarian):
    """Verifies that querying a known ISBN returns structured bibliographic metadata."""
    resp = client.get("/api/books/lookup-isbn/9780134685991", headers=auth_librarian["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["isbn"] == "9780134685991"
    assert "Effective Java" in data["title"]
    assert "Bloch" in data["author"]
    assert data["category"] is not None


def test_isbn_lookup_local_inventory_book(client, db, auth_librarian):
    """Verifies that looking up an existing local catalog ISBN flags exists_locally."""
    with atomic_write(db):
        local_book = Book(
            title="Local Test Robotics",
            author="Dr. Local Author",
            isbn="9780139999991",
            category="Robotics",
            description="Testing local lookup",
        )
        db.add(local_book)
        db.flush()

    resp = client.get("/api/books/lookup-isbn/9780139999991", headers=auth_librarian["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["exists_locally"] is True
    assert data["title"] == "Local Test Robotics"


def test_auto_catalog_book_and_generate_barcodes(client, db, auth_librarian):
    """Verifies atomic creation of book title and physical accession copy barcodes."""
    test_isbn = "9780201633610"
    payload = {
        "isbn": test_isbn,
        "title": "Design Patterns: Elements of Reusable Object-Oriented Software",
        "author": "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
        "category": "Software Engineering",
        "description": "23 classic design patterns reference.",
        "initial_copies": 2,
    }

    resp = client.post("/api/books/auto-catalog", json=payload, headers=auth_librarian["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["isbn"] == test_isbn
    assert data["total_copies"] == 2
    assert len(data["copies"]) == 2
    for copy in data["copies"]:
        assert copy["copy_code"].startswith(f"BC-{data['id']:04d}")
        assert copy["operational_status"] == "available"
