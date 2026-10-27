"""
Automated tests for Stage 3 — Book Catalogue and Physical Inventory APIs.

Coverage:
1. Catalogue listing, pagination, searching, and filtering.
2. Book detail retrieval and missing records.
3. Creating, updating, and archiving catalogue records.
4. ISBN validation and duplicate ISBN conflicts.
5. Adding and updating physical copies.
6. Operational status validation (including strict rejection of 'borrowed' status).
7. Correct availability and inventory counts (dynamic derivation from active loans).
8. Student versus librarian role-based authorization.
9. Unauthenticated access rejections.
10. Historical-record preservation and foreign-key integrity.
11. Database rollback and transaction behavior for failed writes.
"""
from datetime import datetime, date, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.database import atomic_write
from app.models import Book, BookCopy, Loan, User


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def auth_librarian(client, db: Session):
    """Creates a librarian user and configures authentication cookies and CSRF headers."""
    with atomic_write(db):
        user = User(
            email="lib_stage3@library.org",
            full_name="Stage3 Librarian",
            hashed_password=hash_password("Stage3LibPass123!"),
            role="librarian",
            is_active=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id

    token = create_access_token(user_id=user_id, role="librarian")
    csrf_val = "stage3-csrf-token-librarian"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user_id": user_id,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


@pytest.fixture
def auth_student(client, db: Session):
    """Creates a student user and configures authentication cookies and CSRF headers."""
    with atomic_write(db):
        user = User(
            email="stud_stage3@university.edu",
            full_name="Stage3 Student",
            hashed_password=hash_password("Stage3StudPass123!"),
            role="student",
            is_active=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id

    token = create_access_token(user_id=user_id, role="student")
    csrf_val = "stage3-csrf-token-student"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user_id": user_id,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


@pytest.fixture
def seed_catalogue(db: Session):
    """Seeds catalogue books with various categories and physical copies."""
    with atomic_write(db):
        b1 = Book(
            title="Clean Code",
            author="Robert C. Martin",
            isbn="9780132350884",
            category="Software Engineering",
            description="A Handbook of Agile Software Craftsmanship",
            is_archived=False,
        )
        b2 = Book(
            title="Design Patterns",
            author="Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
            isbn="9780201633610",
            category="Software Engineering",
            description="Elements of Reusable Object-Oriented Software",
            is_archived=False,
        )
        b3 = Book(
            title="Introduction to Algorithms",
            author="Thomas H. Cormen",
            isbn="9780262033848",
            category="Computer Science",
            description="Comprehensive algorithms guide",
            is_archived=False,
        )
        b_archived = Book(
            title="Legacy Operating Systems",
            author="Old Author",
            isbn="9780111111118",
            category="Computer Science",
            description="Out of print and retired",
            is_archived=True,
        )
        db.add_all([b1, b2, b3, b_archived])
        db.flush()

        # Add physical copies to b1
        c1 = BookCopy(book_id=b1.id, copy_code="CC-001", operational_status="available")
        c2 = BookCopy(book_id=b1.id, copy_code="CC-002", operational_status="available")
        c3 = BookCopy(book_id=b1.id, copy_code="CC-003", operational_status="maintenance")

        # Add physical copies to b2
        c4 = BookCopy(book_id=b2.id, copy_code="DP-001", operational_status="available")

        db.add_all([c1, c2, c3, c4])
        db.flush()

        data = {
            "b1_id": b1.id,
            "b2_id": b2.id,
            "b3_id": b3.id,
            "b_archived_id": b_archived.id,
            "c1_id": c1.id,
            "c2_id": c2.id,
            "c3_id": c3.id,
            "c4_id": c4.id,
        }
    return data


# ── 1. Catalogue Listing, Search, Filter & Pagination ─────────────────────────

def test_list_books_pagination(client, auth_student, seed_catalogue):
    """Verifies pagination parameters page, page_size, total, and total_pages."""
    resp = client.get("/api/books?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total"] == 3  # b_archived excluded for students
    assert data["total_pages"] == 2
    assert len(data["items"]) == 2


def test_list_books_search_by_title_author_isbn(client, auth_student, seed_catalogue):
    """Verifies case-insensitive search by title, author, and ISBN."""
    # Search by title
    r1 = client.get("/api/books?search=clean")
    assert r1.status_code == 200
    assert len(r1.json()["items"]) == 1
    assert r1.json()["items"][0]["title"] == "Clean Code"

    # Search by author
    r2 = client.get("/api/books?search=Cormen")
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1
    assert r2.json()["items"][0]["author"] == "Thomas H. Cormen"

    # Search by ISBN
    r3 = client.get("/api/books?search=0201633610")
    assert r3.status_code == 200
    assert len(r3.json()["items"]) == 1
    assert r3.json()["items"][0]["title"] == "Design Patterns"


def test_list_books_filter_by_category(client, auth_student, seed_catalogue):
    """Verifies filtering by category."""
    resp = client.get("/api/books?category=Software%20Engineering")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["category"] == "Software Engineering"


def test_student_cannot_view_archived_books(client, auth_student, seed_catalogue):
    """Students should never receive archived books even with include_archived=true."""
    resp = client.get("/api/books?include_archived=true")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()["items"]]
    assert seed_catalogue["b_archived_id"] not in ids


def test_librarian_can_view_archived_books(client, auth_librarian, seed_catalogue):
    """Librarians can view archived books when include_archived=true."""
    resp = client.get("/api/books?include_archived=true")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()["items"]]
    assert seed_catalogue["b_archived_id"] in ids


# ── 2. Book Detail Retrieval ──────────────────────────────────────────────────

def test_get_book_detail_success(client, auth_student, seed_catalogue):
    """Verifies detailed book retrieval including copies list and counts."""
    book_id = seed_catalogue["b1_id"]
    resp = client.get(f"/api/books/{book_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == book_id
    assert data["title"] == "Clean Code"
    assert data["total_copies"] == 3
    assert data["available_copies"] == 2  # 2 available, 1 maintenance
    assert len(data["copies"]) == 3


def test_get_book_detail_not_found(client, auth_student):
    """Verifies 404 response for nonexistent book ID."""
    resp = client.get("/api/books/999999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_student_cannot_view_archived_book_detail(client, auth_student, seed_catalogue):
    """Archived books return 404 to students."""
    archived_id = seed_catalogue["b_archived_id"]
    r_stud = client.get(f"/api/books/{archived_id}")
    assert r_stud.status_code == 404
    assert "not found" in r_stud.json()["detail"].lower()


def test_librarian_can_view_archived_book_detail(client, auth_librarian, seed_catalogue):
    """Archived books return 200 to librarians."""
    archived_id = seed_catalogue["b_archived_id"]
    r_lib = client.get(f"/api/books/{archived_id}")
    assert r_lib.status_code == 200
    assert r_lib.json()["is_archived"] is True


# ── 3. Creating, Updating, and Archiving Books ─────────────────────────────────

def test_librarian_create_book_success(client, auth_librarian):
    """Librarian can create a book title with valid data."""
    payload = {
        "title": "Refactoring: Improving the Design of Existing Code",
        "author": "Martin Fowler",
        "isbn": "978-0201485677",
        "category": "Software Engineering",
        "description": "Improving the design of existing code",
    }
    resp = client.post(
        "/api/books",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == payload["title"]
    assert data["author"] == payload["author"]
    assert data["isbn"] == "9780201485677"
    assert data["total_copies"] == 0
    assert data["available_copies"] == 0
    assert data["is_archived"] is False


def test_create_book_duplicate_isbn_conflict(client, auth_librarian, seed_catalogue):
    """Duplicate ISBN triggers 409 Conflict."""
    payload = {
        "title": "Clean Code Clone",
        "author": "Someone Else",
        "isbn": "978-0132350884",  # Already used by Clean Code
        "category": "Software Engineering",
    }
    resp = client.post(
        "/api/books",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_create_book_invalid_isbn_validation(client, auth_librarian):
    """Malformed or invalid checksum ISBNs trigger 422 Unprocessable Entity."""
    payload = {
        "title": "Invalid ISBN Book",
        "author": "Author",
        "isbn": "978-0132350889",  # Invalid checksum digit
        "category": "Testing",
    }
    resp = client.post(
        "/api/books",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 422
    assert "checksum" in resp.text.lower() or "isbn" in resp.text.lower()


def test_update_book_metadata(client, auth_librarian, seed_catalogue):
    """Librarian can update title, category, and description."""
    book_id = seed_catalogue["b2_id"]
    payload = {
        "title": "Design Patterns: Elements of Reusable OO Software",
        "category": "Architecture",
    }
    resp = client.patch(
        f"/api/books/{book_id}",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == payload["title"]
    assert data["category"] == "Architecture"


def test_update_book_duplicate_isbn_conflict(client, auth_librarian, seed_catalogue):
    """Updating a book's ISBN to an existing book's ISBN triggers 409 Conflict."""
    book_id = seed_catalogue["b2_id"]
    payload = {
        "isbn": "978-0132350884",  # Belongs to b1
    }
    resp = client.patch(
        f"/api/books/{book_id}",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_archive_book_soft_deletes_record(client, auth_librarian, seed_catalogue):
    """Soft-archiving a book preserves copies and sets is_archived=True."""
    book_id = seed_catalogue["b1_id"]
    resp = client.post(
        f"/api/books/{book_id}/archive",
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == book_id
    assert data["is_archived"] is True

    # Check that DELETE endpoint also archives safely
    resp_del = client.delete(
        f"/api/books/{seed_catalogue['b2_id']}",
        headers=auth_librarian["headers"],
    )
    assert resp_del.status_code == 200
    assert resp_del.json()["is_archived"] is True


# ── 4. Physical Copy Inventory APIs ───────────────────────────────────────────

def test_list_copies_for_book(client, auth_student, seed_catalogue):
    """Lists physical copies of a book with operational and borrowing status."""
    book_id = seed_catalogue["b1_id"]
    resp = client.get(f"/api/books/{book_id}/copies")
    assert resp.status_code == 200
    copies = resp.json()
    assert len(copies) == 3
    codes = [c["copy_code"] for c in copies]
    assert "CC-001" in codes
    assert "CC-002" in codes
    assert "CC-003" in codes


def test_add_copy_success(client, auth_librarian, seed_catalogue):
    """Librarian can add a physical copy to an active book."""
    book_id = seed_catalogue["b3_id"]
    payload = {
        "copy_code": "ALGO-001",
        "operational_status": "available",
        "notes": "First edition, shelf A4",
    }
    resp = client.post(
        f"/api/books/{book_id}/copies",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["copy_code"] == "ALGO-001"
    assert data["operational_status"] == "available"
    assert data["is_borrowed"] is False
    assert data["effective_status"] == "available"


def test_add_copy_duplicate_code_conflict(client, auth_librarian, seed_catalogue):
    """Adding a copy with a duplicate copy code triggers 409 Conflict."""
    book_id = seed_catalogue["b3_id"]
    payload = {
        "copy_code": "CC-001",  # Already exists for b1
        "operational_status": "available",
    }
    resp = client.post(
        f"/api/books/{book_id}/copies",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_cannot_add_copy_to_archived_book(client, auth_librarian, seed_catalogue):
    """Cannot add a copy to an archived book (400 Bad Request)."""
    archived_id = seed_catalogue["b_archived_id"]
    payload = {
        "copy_code": "ARCH-999",
        "operational_status": "available",
    }
    resp = client.post(
        f"/api/books/{archived_id}/copies",
        json=payload,
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 400
    assert "archived" in resp.json()["detail"].lower()


# ── 5. Operational Status Validation ──────────────────────────────────────────

def test_operational_status_cannot_be_borrowed(client, auth_librarian, seed_catalogue):
    """
    Passing 'borrowed' as operational_status must be rejected with 422,
    as borrowing state is dynamically derived.
    """
    book_id = seed_catalogue["b1_id"]
    # In copy creation
    resp = client.post(
        f"/api/books/{book_id}/copies",
        json={"copy_code": "CC-BAD-STATUS", "operational_status": "borrowed"},
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 422
    assert "borrowed" in resp.text.lower()

    # In copy update
    copy_id = seed_catalogue["c1_id"]
    resp_update = client.patch(
        f"/api/copies/{copy_id}",
        json={"operational_status": "borrowed"},
        headers=auth_librarian["headers"],
    )
    assert resp_update.status_code == 422
    assert "borrowed" in resp_update.text.lower()


def test_operational_status_invalid_value_rejected(client, auth_librarian, seed_catalogue):
    """Invalid operational status strings trigger 422 Unprocessable Entity."""
    copy_id = seed_catalogue["c1_id"]
    resp = client.patch(
        f"/api/copies/{copy_id}",
        json={"operational_status": "demolished"},
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 422


def test_update_copy_operational_status_valid(client, auth_librarian, seed_catalogue):
    """Valid status transitions (e.g. available -> maintenance -> lost) succeed."""
    copy_id = seed_catalogue["c1_id"]

    # Change to maintenance
    r1 = client.patch(
        f"/api/copies/{copy_id}",
        json={"operational_status": "maintenance", "notes": "Page 42 torn"},
        headers=auth_librarian["headers"],
    )
    assert r1.status_code == 200
    assert r1.json()["operational_status"] == "maintenance"
    assert r1.json()["notes"] == "Page 42 torn"

    # Change to lost
    r2 = client.patch(
        f"/api/copies/{copy_id}",
        json={"operational_status": "lost"},
        headers=auth_librarian["headers"],
    )
    assert r2.status_code == 200
    assert r2.json()["operational_status"] == "lost"


# ── 6. Derived Borrowing Status & Inventory Counts ─────────────────────────────

def test_dynamic_borrowed_status_and_inventory_counts(client, auth_librarian, seed_catalogue, db: Session):
    """
    Verifies that:
    1. Active loan sets is_borrowed=True and effective_status='borrowed'.
    2. Operational_status remains 'available'.
    3. Book listing and detail available_copies dynamically decrease.
    4. Returning the loan restores available_copies count and unsets is_borrowed.
    """
    book_id = seed_catalogue["b1_id"]
    copy_id = seed_catalogue["c1_id"]

    # Initial state: b1 has 3 copies (2 available, 1 maintenance)
    detail_init = client.get(f"/api/books/{book_id}").json()
    assert detail_init["total_copies"] == 3
    assert detail_init["available_copies"] == 2

    # Create an active loan directly in the database
    db.info["_in_atomic_write"] = True
    with atomic_write(db):
        loan = Loan(
            student_id=auth_librarian["user_id"],  # any user
            copy_id=copy_id,
            issued_by_id=auth_librarian["user_id"],
            due_date=date.today() + timedelta(days=14),
            returned_at=None,  # Active loan
        )
        db.add(loan)
        db.flush()
        loan_id = loan.id

    # Check copy directly
    copy_resp = client.get(f"/api/copies/{copy_id}").json()
    assert copy_resp["is_borrowed"] is True
    assert copy_resp["effective_status"] == "borrowed"
    assert copy_resp["operational_status"] == "available"

    # Check book detail count
    detail_loaned = client.get(f"/api/books/{book_id}").json()
    assert detail_loaned["total_copies"] == 3
    assert detail_loaned["available_copies"] == 1  # Decreased by 1

    # Check book list count
    list_resp = client.get(f"/api/books?search=Clean%20Code").json()
    assert list_resp["items"][0]["available_copies"] == 1

    # Return loan
    db.info["_in_atomic_write"] = True
    with atomic_write(db):
        db_loan = db.execute(select(Loan).where(Loan.id == loan_id)).scalar_one()
        db_loan.returned_at = datetime.utcnow()
        db.flush()

    # Verify counts restored
    copy_resp_after = client.get(f"/api/copies/{copy_id}").json()
    assert copy_resp_after["is_borrowed"] is False
    assert copy_resp_after["effective_status"] == "available"

    detail_returned = client.get(f"/api/books/{book_id}").json()
    assert detail_returned["available_copies"] == 2


# ── 7. Role-Based Access Control ──────────────────────────────────────────────

def test_student_forbidden_from_librarian_endpoints(client, auth_student, seed_catalogue):
    """Students receive 403 Forbidden on write operations."""
    headers = auth_student["headers"]
    book_id = seed_catalogue["b1_id"]
    copy_id = seed_catalogue["c1_id"]

    # Create book
    r1 = client.post("/api/books", json={"title": "T", "author": "A", "category": "C"}, headers=headers)
    assert r1.status_code == 403

    # Update book
    r2 = client.patch(f"/api/books/{book_id}", json={"title": "New Title"}, headers=headers)
    assert r2.status_code == 403

    # Archive book
    r3 = client.post(f"/api/books/{book_id}/archive", headers=headers)
    assert r3.status_code == 403

    # Add copy
    r4 = client.post(f"/api/books/{book_id}/copies", json={"copy_code": "NEW-001"}, headers=headers)
    assert r4.status_code == 403

    # Update copy
    r5 = client.patch(f"/api/copies/{copy_id}", json={"operational_status": "maintenance"}, headers=headers)
    assert r5.status_code == 403

    # Retire copy
    r6 = client.post(f"/api/copies/{copy_id}/retire", headers=headers)
    assert r6.status_code == 403


def test_unauthenticated_requests_rejected(client, seed_catalogue):
    """Unauthenticated requests receive 401 Unauthorized."""
    client.cookies.clear()
    book_id = seed_catalogue["b1_id"]

    assert client.get("/api/books").status_code == 401
    assert client.get(f"/api/books/{book_id}").status_code == 401
    assert client.get(f"/api/books/{book_id}/copies").status_code == 401
    assert client.get(f"/api/copies/{seed_catalogue['c1_id']}").status_code == 401

    # For mutation requests, pass CSRF token so request passes CSRF middleware to reach auth check
    csrf_val = "unauth-csrf-token"
    client.cookies.set("csrf_token", csrf_val)
    resp = client.post(
        "/api/books",
        json={"title": "T", "author": "A", "category": "C"},
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val},
    )
    assert resp.status_code == 401


# ── 8. Historical Records & Data Integrity ─────────────────────────────────────

def test_cannot_retire_copy_with_active_loan(client, auth_librarian, seed_catalogue, db: Session):
    """Cannot retire or delete a physical copy that currently has an active loan."""
    copy_id = seed_catalogue["c1_id"]

    # Issue active loan
    db.info["_in_atomic_write"] = True
    with atomic_write(db):
        loan = Loan(
            student_id=auth_librarian["user_id"],
            copy_id=copy_id,
            issued_by_id=auth_librarian["user_id"],
            due_date=date.today() + timedelta(days=7),
            returned_at=None,
        )
        db.add(loan)
        db.flush()

    # Attempt to retire
    resp = client.post(f"/api/copies/{copy_id}/retire", headers=auth_librarian["headers"])
    assert resp.status_code == 409
    assert "active loan" in resp.json()["detail"].lower()

    # Attempt to delete
    resp_del = client.delete(f"/api/copies/{copy_id}", headers=auth_librarian["headers"])
    assert resp_del.status_code == 409
    assert "active loan" in resp_del.json()["detail"].lower()


def test_preserve_historical_loans_prevent_copy_deletion(client, auth_librarian, seed_catalogue, db: Session):
    """
    Physical deletion of a copy with past loan history is rejected with 409,
    requiring the copy to be retired instead.
    """
    copy_id = seed_catalogue["c2_id"]

    # Create a returned (historical) loan
    db.info["_in_atomic_write"] = True
    with atomic_write(db):
        loan = Loan(
            student_id=auth_librarian["user_id"],
            copy_id=copy_id,
            issued_by_id=auth_librarian["user_id"],
            due_date=date.today() - timedelta(days=10),
            returned_at=datetime.utcnow() - timedelta(days=5),
        )
        db.add(loan)
        db.flush()

    # Attempt physical deletion
    resp_del = client.delete(f"/api/copies/{copy_id}", headers=auth_librarian["headers"])
    assert resp_del.status_code == 409
    assert "retire the copy instead" in resp_del.json()["detail"].lower()

    # Retiring the copy succeeds
    resp_retire = client.post(f"/api/copies/{copy_id}/retire", headers=auth_librarian["headers"])
    assert resp_retire.status_code == 200
    assert resp_retire.json()["operational_status"] == "retired"


def test_unreferenced_copy_deletion_succeeds(client, auth_librarian, seed_catalogue):
    """A copy that has never had any loans can be physically deleted."""
    copy_id = seed_catalogue["c3_id"]
    resp = client.delete(f"/api/copies/{copy_id}", headers=auth_librarian["headers"])
    assert resp.status_code == 200
    assert "deleted successfully" in resp.json()["message"].lower()

    # Verify copy no longer exists
    assert client.get(f"/api/copies/{copy_id}").status_code == 404


# ── 9. Transaction Rollback on Failure ─────────────────────────────────────────

def test_transaction_rollback_on_failed_write(client, auth_librarian, seed_catalogue, db: Session):
    """
    Verifies that a failed write operation (duplicate code/ISBN)
    rolls back completely, leaving no partial records.
    """
    book_id = seed_catalogue["b1_id"]

    # Initial count of copies
    init_copies = db.execute(select(BookCopy).where(BookCopy.book_id == book_id)).scalars().all()
    count_before = len(init_copies)

    # Attempt adding duplicate copy code
    resp = client.post(
        f"/api/books/{book_id}/copies",
        json={"copy_code": "CC-001", "operational_status": "available"},
        headers=auth_librarian["headers"],
    )
    assert resp.status_code == 409

    # Verify database state was untouched
    count_after = db.execute(select(BookCopy).where(BookCopy.book_id == book_id)).scalars().all()
    assert len(count_after) == count_before
