"""
Tests for physical shelf-reading audit, misplaced monograph routing, and exit security anti-theft sensors.
"""
from datetime import datetime, timedelta
import pytest
from sqlalchemy.orm import Session
from app.models import User, Book, BookCopy, Loan, InventoryEvent
from app.auth import create_access_token, hash_password
from app.database import atomic_write


@pytest.fixture
def auth_librarian(client, db: Session):
    with atomic_write(db):
        user = User(
            email="audit_librarian@library.org",
            full_name="Shelf Audit Specialist",
            hashed_password=hash_password("AuditPass123!"),
            role="librarian",
            is_active=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id

    token = create_access_token(user_id=user_id, role="librarian")
    csrf_val = "audit-csrf-token-val"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user_id": user_id,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


def test_shelf_reading_audit_verified_in_place(client, db: Session, auth_librarian):
    """Verifies that scanning a Computer Science book in Aisle 2A reports verified in place."""
    with atomic_write(db):
        book = Book(
            title="Introduction to Automata Theory",
            author="Hopcroft & Ullman",
            category="Computer Science",
        )
        db.add(book)
        db.flush()
        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-CS-01",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

    response = client.post(
        "/api/books/shelf-audit",
        json={
            "audited_aisle": "Aisle 2A",
            "barcode": "BC-TEST-CS-01",
        },
        headers=auth_librarian["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "verified_in_place"
    assert data["copy_code"] == "BC-TEST-CS-01"
    assert data["expected_aisle"] == "Aisle 2A"
    assert "VERIFIED IN PLACE" in data["message"]


def test_shelf_reading_audit_misplaced_detection(client, db: Session, auth_librarian):
    """Verifies that scanning a Computer Science book in Aisle 1A (Mathematics) detects misplacement."""
    with atomic_write(db):
        book = Book(
            title="Compiler Design Principles",
            author="Aho & Ullman",
            category="Computer Science",
        )
        db.add(book)
        db.flush()
        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-MISP-01",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

    response = client.post(
        "/api/books/shelf-audit",
        json={
            "audited_aisle": "Aisle 1A",  # Wrong aisle!
            "barcode": "BC-TEST-MISP-01",
        },
        headers=auth_librarian["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "misplaced"
    assert data["audited_aisle"] == "Aisle 1A"
    assert data["expected_aisle"] == "Aisle 2A"
    assert "MISPLACED MONOGRAPH DETECTED" in data["message"]
    assert "Route to Reshelving Cart" in data["action_suggested"]


def test_shelf_reading_audit_recovers_missing_book(client, db: Session, auth_librarian):
    """Verifies that a book flagged under maintenance is automatically recovered when scanned on shelf."""
    with atomic_write(db):
        book = Book(
            title="Real Mathematical Analysis",
            author="Charles Pugh",
            category="Mathematics",
        )
        db.add(book)
        db.flush()
        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-RECOV-01",
            operational_status="maintenance",
            notes="Flagged missing by patron",
        )
        db.add(copy)
        db.flush()

    response = client.post(
        "/api/books/shelf-audit",
        json={
            "audited_aisle": "Aisle 1A",  # Correct Math aisle
            "barcode": "BC-TEST-RECOV-01",
        },
        headers=auth_librarian["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recovered"
    assert "RECOVERED" in data["message"]

    # Verify db status restored
    db.refresh(copy)
    assert copy.operational_status == "available"


def test_reshelve_action_buffer_flow(client, db: Session, auth_librarian):
    """Tests loading a copy onto the mobile reshelving cart and then completing restock."""
    with atomic_write(db):
        book = Book(
            title="Distributed Systems Engineering",
            author="George Coulouris",
            category="Distributed Systems",
        )
        db.add(book)
        db.flush()
        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-CART-01",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

    # Step 1: Load to cart
    res1 = client.post(
        "/api/books/reshelve-action",
        json={
            "copy_code": "BC-TEST-CART-01",
            "action": "route_to_cart",
        },
        headers=auth_librarian["headers"],
    )
    assert res1.status_code == 200
    assert res1.json()["operational_status"] == "in_reshelving"

    # Step 2: Restock on shelf
    res2 = client.post(
        "/api/books/reshelve-action",
        json={
            "copy_code": "BC-TEST-CART-01",
            "action": "mark_on_shelf",
        },
        headers=auth_librarian["headers"],
    )
    assert res2.status_code == 200
    assert res2.json()["operational_status"] == "available"


def test_exit_security_gate_unauthorized_triggers_alarm(client, db: Session):
    """Verifies that an unborrowed book passing through exit pedestals triggers high-frequency alarm."""
    with atomic_write(db):
        book = Book(
            title="Advanced Operating Systems",
            author="Andrew Tanenbaum",
            category="Distributed Systems",
        )
        db.add(book)
        db.flush()
        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-ALARM-01",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

    csrf_val = "exit-csrf-val"
    client.cookies.set("csrf_token", csrf_val)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val}

    response = client.post(
        "/api/circulation/verify-exit-gate",
        json={"copy_code": "BC-TEST-ALARM-01"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["allow_exit"] is False
    assert data["alarm_triggered"] is True
    assert data["status"] == "UNAUTHORIZED_ALARM"
    assert "SECURITY ALARM" in data["message"]


def test_exit_security_gate_authorized_loan_permits_exit(client, db: Session):
    """Verifies that a book with an active loan passes through exit pedestals silently."""
    with atomic_write(db):
        student = User(
            email="borrower_student@library.org",
            full_name="Borrowing Student",
            hashed_password=hash_password("StudentPass123!"),
            role="student",
            is_active=True,
        )
        librarian = User(
            email="gate_librarian@library.org",
            full_name="Gate Attendant",
            hashed_password=hash_password("AttendantPass123!"),
            role="librarian",
            is_active=True,
        )
        book = Book(
            title="Clean Code Foundations",
            author="Robert C. Martin",
            category="Software Engineering",
        )
        db.add_all([student, librarian, book])
        db.flush()

        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-GATEPASS-01",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        loan = Loan(
            student_id=student.id,
            copy_id=copy.id,
            issued_by_id=librarian.id,
            due_date=datetime.utcnow().date() + timedelta(days=14),
        )
        db.add(loan)
        db.flush()

    csrf_val = "exit-csrf-val"
    client.cookies.set("csrf_token", csrf_val)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val}

    response = client.get(
        "/api/circulation/verify-exit-gate/BC-TEST-GATEPASS-01",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["allow_exit"] is True
    assert data["alarm_triggered"] is False
    assert data["status"] == "AUTHORIZED_CHECKOUT"
    assert data["loan_id"] == loan.id
    assert data["borrower_name"] == "Borrowing Student"


def test_exit_gate_hold_checkout_incomplete_advisory(client, db: Session):
    """Verifies that an unborrowed book with an active hold issues a friendly advisory rather than theft alarm."""
    from app.models import BookHold
    with atomic_write(db):
        student = User(
            email="innocent_student@library.org",
            full_name="Innocent Student",
            hashed_password=hash_password("Pass123!"),
            role="student",
            is_active=True,
        )
        book = Book(
            title="Design Patterns Elements",
            author="Gang of Four",
            category="Software Engineering",
        )
        db.add_all([student, book])
        db.flush()

        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-HELD-01",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        hold = BookHold(
            book_id=book.id,
            user_id=student.id,
            copy_id=copy.id,
            status="ready_for_pickup",
        )
        db.add(hold)
        db.flush()

    csrf_val = "exit-csrf-val"
    client.cookies.set("csrf_token", csrf_val)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val}

    response = client.get(
        "/api/circulation/verify-exit-gate/BC-TEST-HELD-01",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["allow_exit"] is False
    assert data["alarm_triggered"] is False  # NOT A THEFT ALARM!
    assert data["advisory_only"] is True
    assert data["status"] == "HOLD_CHECKOUT_INCOMPLETE"
    assert "Innocent Student" in data["message"]


def test_self_checkout_exact_match(client, db: Session):
    """Verifies that a student scanning their assigned reserved copy receives an immediate loan."""
    from app.models import BookHold
    with atomic_write(db):
        student = User(
            email="self_checkout_student@library.org",
            full_name="Self Checkout Patron",
            hashed_password=hash_password("Pass123!"),
            role="student",
            is_active=True,
        )
        book = Book(
            title="Operating Systems Principles",
            author="Silberschatz",
            category="Distributed Systems",
        )
        db.add_all([student, book])
        db.flush()

        copy = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-EXACT-01",
            operational_status="available",
        )
        db.add(copy)
        db.flush()

        hold = BookHold(
            book_id=book.id,
            user_id=student.id,
            copy_id=copy.id,
            status="ready_for_pickup",
        )
        db.add(hold)
        db.flush()

    csrf_val = "kiosk-csrf-val"
    client.cookies.set("csrf_token", csrf_val)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val}

    response = client.post(
        "/api/circulation/self-checkout",
        json={
            "student_id_or_email": "self_checkout_student@library.org",
            "copy_code": "BC-TEST-EXACT-01",
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "LOAN_ISSUED"
    assert data["swap_applied"] is False
    assert data["loan_id"] is not None


def test_self_checkout_smart_copy_swapping(client, db: Session):
    """Verifies that grabbing an unreserved sibling copy of the same book dynamically swaps and issues loan."""
    from app.models import BookHold
    with atomic_write(db):
        student = User(
            email="swapper_student@library.org",
            full_name="Swapping Student",
            hashed_password=hash_password("Pass123!"),
            role="student",
            is_active=True,
        )
        book = Book(
            title="Database System Concepts",
            author="Silberschatz",
            category="Distributed Systems",
        )
        db.add_all([student, book])
        db.flush()

        # Assigned copy 1
        copy1 = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-SWAP-01",
            operational_status="available",
        )
        # Sibling copy 2 (available on shelf)
        copy2 = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-SWAP-02",
            operational_status="available",
        )
        db.add_all([copy1, copy2])
        db.flush()

        # Student's hold was pointing to copy 1
        hold = BookHold(
            book_id=book.id,
            user_id=student.id,
            copy_id=copy1.id,
            status="ready_for_pickup",
        )
        db.add(hold)
        db.flush()

    csrf_val = "kiosk-csrf-val"
    client.cookies.set("csrf_token", csrf_val)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val}

    # Student accidentally scanned copy 2!
    response = client.post(
        "/api/circulation/self-checkout",
        json={
            "student_id_or_email": "swapper_student@library.org",
            "copy_code": "BC-TEST-SWAP-02",
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "SMART_SWAP_ISSUED"
    assert data["swap_applied"] is True
    assert data["copy_code"] == "BC-TEST-SWAP-02"
    assert data["original_copy_code"] == "BC-TEST-SWAP-01"
    assert "SMART COPY SWAP" in data["message"]

    # Verify hold was rebound and fulfilled
    db.refresh(hold)
    assert hold.copy_id == copy2.id
    assert hold.status == "fulfilled"


def test_self_checkout_wrong_book_mismatch_rejected(client, db: Session):
    """Verifies that grabbing an adjacent different book is rejected with shelf return guidance."""
    from app.models import BookHold
    with atomic_write(db):
        student = User(
            email="wrong_pull_student@library.org",
            full_name="Wrong Pull Student",
            hashed_password=hash_password("Pass123!"),
            role="student",
            is_active=True,
        )
        book_math = Book(
            title="Linear Algebra Principles",
            author="Gilbert Strang",
            category="Mathematics",
        )
        book_cs = Book(
            title="Data Structures in Java",
            author="Mark Weiss",
            category="Computer Science",
        )
        db.add_all([student, book_math, book_cs])
        db.flush()

        copy_math = BookCopy(
            book_id=book_math.id,
            copy_code="BC-TEST-MATH-01",
            operational_status="available",
        )
        copy_cs = BookCopy(
            book_id=book_cs.id,
            copy_code="BC-TEST-CS-99",
            operational_status="available",
        )
        db.add_all([copy_math, copy_cs])
        db.flush()

        # Student reserved the MATH book
        hold = BookHold(
            book_id=book_math.id,
            user_id=student.id,
            copy_id=copy_math.id,
            status="ready_for_pickup",
        )
        db.add(hold)
        db.flush()

    csrf_val = "kiosk-csrf-val"
    client.cookies.set("csrf_token", csrf_val)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val}

    # Student accidentally scanned the CS book!
    response = client.post(
        "/api/circulation/self-checkout",
        json={
            "student_id_or_email": "wrong_pull_student@library.org",
            "copy_code": "BC-TEST-CS-99",
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["status"] == "WRONG_BOOK"
    assert "WRONG TITLE SCANNED" in data["message"]
    assert "Linear Algebra Principles" in data["guidance"]


def test_self_checkout_copy_restricted_held_by_other_patron(client, db: Session):
    """Verifies that grabbing another student's reserved copy is blocked with guidance."""
    from app.models import BookHold
    with atomic_write(db):
        student_a = User(
            email="student_a@library.org",
            full_name="Student Alpha",
            hashed_password=hash_password("Pass123!"),
            role="student",
            is_active=True,
        )
        student_b = User(
            email="student_b@library.org",
            full_name="Student Bravo",
            hashed_password=hash_password("Pass123!"),
            role="student",
            is_active=True,
        )
        book = Book(
            title="Artificial Intelligence Modern Approach",
            author="Russell & Norvig",
            category="Artificial Intelligence",
        )
        db.add_all([student_a, student_b, book])
        db.flush()

        copy_for_b = BookCopy(
            book_id=book.id,
            copy_code="BC-TEST-HELD-B-01",
            operational_status="available",
        )
        db.add(copy_for_b)
        db.flush()

        # Hold belongs to Student Bravo
        hold_b = BookHold(
            book_id=book.id,
            user_id=student_b.id,
            copy_id=copy_for_b.id,
            status="ready_for_pickup",
        )
        db.add(hold_b)
        db.flush()

    csrf_val = "kiosk-csrf-val"
    client.cookies.set("csrf_token", csrf_val)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val}

    # Student Alpha attempts to checkout Student Bravo's copy
    response = client.post(
        "/api/circulation/self-checkout",
        json={
            "student_id_or_email": "student_a@library.org",
            "copy_code": "BC-TEST-HELD-B-01",
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["status"] == "COPY_RESTRICTED"
    assert "Student Bravo" in data["message"]
    assert "COPY RESERVED FOR ANOTHER STUDENT" in data["message"]

