"""
Automated test suite for Stage 4 — Loan Circulation: Issue, Return, and Due-Date Management.

Coverage:
1. Successful issuance and exact 14-calendar-day due dates.
2. Successful return and preservation of historical records.
3. Inactive or invalid student rejection.
4. Non-student user borrowing rejection.
5. Missing, archived, retired, lost, and maintenance copy rejections.
6. Three-loan maximum limit and rejection of a fourth loan.
7. Blocking new loans when any overdue active loan exists.
8. Overdue boundary calculations (today = not overdue, yesterday = overdue).
9. Duplicate issuance and duplicate return rejections.
10. Privacy enforcement (students can view only their own loans; librarians view all).
11. Librarian loan queries, pagination, and multi-field filtering.
12. Dynamic inventory counts reflecting issuance and returns.
13. Transaction rollback on failed issuance or return.
14. Concurrency: concurrent issuance of the same copy and concurrent race for a student's final loan slot.
"""
from datetime import date, datetime, timedelta
from pathlib import Path
import threading
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.auth import create_access_token, hash_password
from app.database import atomic_write, init_db, setup_engine_events
from app.models import Book, BookCopy, Loan, User
from app.services import loans as loans_service
from app.schemas import LoanIssueRequest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def auth_librarian(client, db: Session):
    """Creates a librarian and configures authentication and CSRF headers."""
    user = User(
        email="circ_librarian@library.org",
        full_name="Circulation Librarian",
        hashed_password=hash_password("CircLibPass123!"),
        role="librarian",
        is_active=True,
    )
    db.add(user)
    db.flush()
    user_id = user.id

    token = create_access_token(user_id=user_id, role="librarian")
    csrf_val = "circ-csrf-token-librarian"
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
    """Creates a student user and configures authentication and CSRF headers."""
    user = User(
        email="circ_student1@university.edu",
        full_name="Alice Student",
        hashed_password=hash_password("AlicePass123!"),
        role="student",
        is_active=True,
    )
    db.add(user)
    db.flush()
    user_id = user.id

    token = create_access_token(user_id=user_id, role="student")
    csrf_val = "circ-csrf-token-student1"
    return {
        "user_id": user_id,
        "email": user.email,
        "name": user.full_name,
        "token": token,
        "csrf_val": csrf_val,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


@pytest.fixture
def auth_student_two(client, db: Session):
    """Creates a second student user for privacy testing."""
    user = User(
        email="circ_student2@university.edu",
        full_name="Bob Student",
        hashed_password=hash_password("BobPass123!"),
        role="student",
        is_active=True,
    )
    db.add(user)
    db.flush()
    user_id = user.id

    token = create_access_token(user_id=user_id, role="student")
    csrf_val = "circ-csrf-token-student2"
    return {
        "user_id": user_id,
        "email": user.email,
        "name": user.full_name,
        "token": token,
        "csrf_val": csrf_val,
        "headers": {
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf_val,
        },
    }


@pytest.fixture
def seed_circulation_data(db: Session):
    """Seeds books and physical copies with various operational statuses."""
    book_active = Book(
        title="Domain-Driven Design",
        author="Eric Evans",
        isbn="9780321125217",
        category="Software Architecture",
        is_archived=False,
    )
    book_archived = Book(
        title="Archived COBOL Guide",
        author="Grace Hopper",
        isbn="9780131111111",
        category="Legacy",
        is_archived=True,
    )
    db.add_all([book_active, book_archived])
    db.flush()

    # Available copies
    c_avail1 = BookCopy(book_id=book_active.id, copy_code="DDD-001", operational_status="available")
    c_avail2 = BookCopy(book_id=book_active.id, copy_code="DDD-002", operational_status="available")
    c_avail3 = BookCopy(book_id=book_active.id, copy_code="DDD-003", operational_status="available")
    c_avail4 = BookCopy(book_id=book_active.id, copy_code="DDD-004", operational_status="available")
    c_avail5 = BookCopy(book_id=book_active.id, copy_code="DDD-005", operational_status="available")

    # Non-available copies
    c_maint = BookCopy(book_id=book_active.id, copy_code="DDD-MAINT", operational_status="maintenance")
    c_lost = BookCopy(book_id=book_active.id, copy_code="DDD-LOST", operational_status="lost")
    c_retired = BookCopy(book_id=book_active.id, copy_code="DDD-RETIRED", operational_status="retired")

    # Copy of archived book
    c_arch = BookCopy(book_id=book_archived.id, copy_code="COBOL-001", operational_status="available")

    db.add_all([c_avail1, c_avail2, c_avail3, c_avail4, c_avail5, c_maint, c_lost, c_retired, c_arch])
    db.flush()

    return {
        "book_active_id": book_active.id,
        "book_archived_id": book_archived.id,
        "c_avail1_id": c_avail1.id,
        "c_avail2_id": c_avail2.id,
        "c_avail3_id": c_avail3.id,
        "c_avail4_id": c_avail4.id,
        "c_avail5_id": c_avail5.id,
        "c_maint_id": c_maint.id,
        "c_lost_id": c_lost.id,
        "c_retired_id": c_retired.id,
        "c_arch_id": c_arch.id,
    }


# ── 1. Loan Issuance & Due Date Management ───────────────────────────────────

def test_issue_loan_success_with_14_day_due_date(client, auth_librarian, auth_student, seed_circulation_data):
    """
    Librarian issues a book copy to an eligible student:
    - issued_by_id set from authenticated librarian.
    - due_date exactly 14 calendar days from today.
    - status is 'active', is_overdue is False, returned_at is None.
    """
    payload = {
        "student_id": auth_student["user_id"],
        "copy_id": seed_circulation_data["c_avail1_id"],
    }
    resp = client.post("/api/loans", json=payload, headers=auth_librarian["headers"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["student_id"] == auth_student["user_id"]
    assert data["copy_id"] == seed_circulation_data["c_avail1_id"]
    assert data["issued_by_id"] == auth_librarian["user_id"]
    assert data["returned_at"] is None
    assert data["status"] == "active"
    assert data["is_overdue"] is False
    assert data["book_title"] == "Domain-Driven Design"
    assert data["copy_code"] == "DDD-001"

    expected_due = (date.today() + timedelta(days=14)).isoformat()
    assert data["due_date"] == expected_due

    # Alias /api/loans/issue also functions
    p2 = {
        "student_id": auth_student["user_id"],
        "copy_id": seed_circulation_data["c_avail2_id"],
    }
    r2 = client.post("/api/loans/issue", json=p2, headers=auth_librarian["headers"])
    assert r2.status_code == 201


def test_issue_loan_cannot_tamper_issued_by(client, auth_librarian, auth_student, seed_circulation_data):
    """
    Client attempting to inject an issued_by_id in payload must be ignored or rejected,
    always setting issued_by_id from the authenticated librarian session.
    """
    payload = {
        "student_id": auth_student["user_id"],
        "copy_id": seed_circulation_data["c_avail1_id"],
        "issued_by_id": 9999,  # Malicious attempt to forge librarian
    }
    resp = client.post("/api/loans", json=payload, headers=auth_librarian["headers"])
    assert resp.status_code == 201
    assert resp.json()["issued_by_id"] == auth_librarian["user_id"]


def test_issue_loan_rejects_inactive_student(client, auth_librarian, seed_circulation_data, db: Session):
    """Cannot issue loan to an inactive student account."""
    inactive_student = User(
        email="inactive_stud@uni.edu",
        full_name="Inactive Stud",
        hashed_password=hash_password("Pass123!"),
        role="student",
        is_active=False,
    )
    db.add(inactive_student)
    db.flush()
    stud_id = inactive_student.id

    payload = {"student_id": stud_id, "copy_id": seed_circulation_data["c_avail1_id"]}
    resp = client.post("/api/loans", json=payload, headers=auth_librarian["headers"])
    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower()


def test_issue_loan_rejects_non_student_role(client, auth_librarian, seed_circulation_data):
    """Cannot issue loan to an account that is not a student (e.g. librarian)."""
    payload = {
        "student_id": auth_librarian["user_id"],  # Librarian role
        "copy_id": seed_circulation_data["c_avail1_id"],
    }
    resp = client.post("/api/loans", json=payload, headers=auth_librarian["headers"])
    assert resp.status_code == 400
    assert "student role" in resp.json()["detail"].lower()


def test_issue_loan_rejects_missing_student(client, auth_librarian, seed_circulation_data):
    """404 when student does not exist."""
    payload = {"student_id": 999999, "copy_id": seed_circulation_data["c_avail1_id"]}
    resp = client.post("/api/loans", json=payload, headers=auth_librarian["headers"])
    assert resp.status_code == 404
    assert "student not found" in resp.json()["detail"].lower()


def test_issue_loan_rejects_missing_or_invalid_copies(client, auth_librarian, auth_student, seed_circulation_data):
    """Cannot issue missing, archived, retired, maintenance, or lost copies."""
    stud_id = auth_student["user_id"]
    headers = auth_librarian["headers"]

    # 1. Missing copy
    r1 = client.post("/api/loans", json={"student_id": stud_id, "copy_id": 999999}, headers=headers)
    assert r1.status_code == 404

    # 2. Archived book's copy
    r2 = client.post("/api/loans", json={"student_id": stud_id, "copy_id": seed_circulation_data["c_arch_id"]}, headers=headers)
    assert r2.status_code == 400
    assert "archived" in r2.json()["detail"].lower()

    # 3. Retired copy
    r3 = client.post("/api/loans", json={"student_id": stud_id, "copy_id": seed_circulation_data["c_retired_id"]}, headers=headers)
    assert r3.status_code == 400
    assert "retired" in r3.json()["detail"].lower()

    # 4. Maintenance copy
    r4 = client.post("/api/loans", json={"student_id": stud_id, "copy_id": seed_circulation_data["c_maint_id"]}, headers=headers)
    assert r4.status_code == 400
    assert "maintenance" in r4.json()["detail"].lower()

    # 5. Lost copy
    r5 = client.post("/api/loans", json={"student_id": stud_id, "copy_id": seed_circulation_data["c_lost_id"]}, headers=headers)
    assert r5.status_code == 400
    assert "lost" in r5.json()["detail"].lower()


def test_duplicate_issue_same_copy_rejected(client, auth_librarian, auth_student, auth_student_two, seed_circulation_data):
    """A copy that is already on loan cannot be issued to anyone (409 Conflict)."""
    copy_id = seed_circulation_data["c_avail1_id"]
    payload1 = {"student_id": auth_student["user_id"], "copy_id": copy_id}
    r1 = client.post("/api/loans", json=payload1, headers=auth_librarian["headers"])
    assert r1.status_code == 201

    # Attempt issuing same copy to student 2
    payload2 = {"student_id": auth_student_two["user_id"], "copy_id": copy_id}
    r2 = client.post("/api/loans", json=payload2, headers=auth_librarian["headers"])
    assert r2.status_code == 409
    assert "currently on loan" in r2.json()["detail"].lower()


# ── 2. Borrowing Limits: Max 3 Loans & Overdue Block ──────────────────────────

def test_maximum_three_active_loans_enforced(client, auth_librarian, auth_student, seed_circulation_data):
    """
    A student can borrow at most 3 books. The 4th attempt is rejected with 400 Bad Request.
    """
    stud_id = auth_student["user_id"]
    headers = auth_librarian["headers"]

    # Issue 1st, 2nd, 3rd
    for cid in [seed_circulation_data["c_avail1_id"], seed_circulation_data["c_avail2_id"], seed_circulation_data["c_avail3_id"]]:
        res = client.post("/api/loans", json={"student_id": stud_id, "copy_id": cid}, headers=headers)
        assert res.status_code == 201

    # Attempt 4th
    res_fourth = client.post("/api/loans", json={"student_id": stud_id, "copy_id": seed_circulation_data["c_avail4_id"]}, headers=headers)
    assert res_fourth.status_code == 400
    assert "maximum" in res_fourth.json()["detail"].lower() or "limit" in res_fourth.json()["detail"].lower()


def test_overdue_active_loan_blocks_new_issuance(client, auth_librarian, auth_student, seed_circulation_data, db: Session):
    """
    If a student has ANY overdue active loan, new loan issuance is rejected with 400 Bad Request.
    """
    stud_id = auth_student["user_id"]
    headers = auth_librarian["headers"]

    # Seed an overdue active loan directly in database
    overdue_loan = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail1_id"],
        issued_by_id=auth_librarian["user_id"],
        issued_at=datetime.utcnow() - timedelta(days=20),
        due_date=date.today() - timedelta(days=6),  # 6 days overdue
        returned_at=None,
    )
    db.add(overdue_loan)
    db.flush()

    # Attempt to borrow another copy
    payload = {"student_id": stud_id, "copy_id": seed_circulation_data["c_avail2_id"]}
    resp = client.post("/api/loans", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "overdue" in resp.json()["detail"].lower()


def test_returned_past_overdue_does_not_block_new_issuance(client, auth_librarian, auth_student, seed_circulation_data, db: Session):
    """
    A previously overdue loan that has been returned must NOT block new borrowing.
    """
    stud_id = auth_student["user_id"]
    headers = auth_librarian["headers"]

    returned_overdue_loan = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail1_id"],
        issued_by_id=auth_librarian["user_id"],
        issued_at=datetime.utcnow() - timedelta(days=20),
        due_date=date.today() - timedelta(days=6),
        returned_at=datetime.utcnow() - timedelta(days=2),  # Returned!
    )
    db.add(returned_overdue_loan)
    db.flush()

    # Should succeed
    payload = {"student_id": stud_id, "copy_id": seed_circulation_data["c_avail2_id"]}
    resp = client.post("/api/loans", json=payload, headers=headers)
    assert resp.status_code == 201


# ── 3. Loan Return Operations ─────────────────────────────────────────────────

def test_return_active_loan_success(client, auth_librarian, auth_student, seed_circulation_data):
    """
    Librarian returns an active loan:
    - returned_at timestamp recorded.
    - Historical data (student, copy, issued_by, issued_at, due_date) preserved.
    - Status changes from 'active' to 'returned'.
    """
    headers = auth_librarian["headers"]
    # 1. Issue loan
    issue_resp = client.post(
        "/api/loans",
        json={"student_id": auth_student["user_id"], "copy_id": seed_circulation_data["c_avail1_id"]},
        headers=headers,
    )
    assert issue_resp.status_code == 201
    loan_id = issue_resp.json()["id"]

    # 2. Return loan
    ret_resp = client.post(f"/api/loans/{loan_id}/return", headers=headers)
    assert ret_resp.status_code == 200
    ret_data = ret_resp.json()
    assert ret_data["id"] == loan_id
    assert ret_data["returned_at"] is not None
    assert ret_data["status"] == "returned"
    assert ret_data["is_overdue"] is False
    assert ret_data["issued_at"] == issue_resp.json()["issued_at"]
    assert ret_data["due_date"] == issue_resp.json()["due_date"]
    assert ret_data["student_id"] == auth_student["user_id"]
    assert ret_data["copy_id"] == seed_circulation_data["c_avail1_id"]


def test_duplicate_return_attempt_rejected(client, auth_librarian, auth_student, seed_circulation_data):
    """Returning an already-returned loan must be rejected with 409 Conflict."""
    headers = auth_librarian["headers"]
    issue_resp = client.post(
        "/api/loans",
        json={"student_id": auth_student["user_id"], "copy_id": seed_circulation_data["c_avail1_id"]},
        headers=headers,
    )
    loan_id = issue_resp.json()["id"]

    # 1st return succeeds
    r1 = client.post(f"/api/loans/{loan_id}/return", headers=headers)
    assert r1.status_code == 200

    # 2nd return rejected with 409
    r2 = client.post(f"/api/loans/{loan_id}/return", headers=headers)
    assert r2.status_code == 409
    assert "already been returned" in r2.json()["detail"].lower()


def test_return_nonexistent_loan_returns_404(client, auth_librarian):
    """Returning a nonexistent loan returns 404."""
    resp = client.post("/api/loans/999999/return", headers=auth_librarian["headers"])
    assert resp.status_code == 404


def test_student_unauthorized_to_issue_or_return_loans(client, auth_student, seed_circulation_data):
    """Students cannot access loan issue or return endpoints (403 Forbidden)."""
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])
    headers = auth_student["headers"]

    # Attempt issue
    r_issue = client.post(
        "/api/loans",
        json={"student_id": auth_student["user_id"], "copy_id": seed_circulation_data["c_avail1_id"]},
        headers=headers,
    )
    assert r_issue.status_code == 403

    # Attempt return
    r_ret = client.post("/api/loans/1/return", headers=headers)
    assert r_ret.status_code == 403


# ── 4. Overdue Boundary Calculations ──────────────────────────────────────────

def test_overdue_boundary_logic(client, auth_librarian, auth_student, seed_circulation_data, db: Session):
    """
    Validates boundary logic:
    - due_date == today: active, not overdue.
    - due_date == today - 1 day: overdue.
    - due_date == today + 1 day: active, not overdue.
    """
    today = date.today()
    stud_id = auth_student["user_id"]
    lib_id = auth_librarian["user_id"]

    # Loan due today
    l_today = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail1_id"],
        issued_by_id=lib_id,
        issued_at=datetime.utcnow() - timedelta(days=14),
        due_date=today,
        returned_at=None,
    )
    # Loan due yesterday
    l_yesterday = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail2_id"],
        issued_by_id=lib_id,
        issued_at=datetime.utcnow() - timedelta(days=15),
        due_date=today - timedelta(days=1),
        returned_at=None,
    )
    # Loan due tomorrow
    l_tomorrow = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail3_id"],
        issued_by_id=lib_id,
        issued_at=datetime.utcnow() - timedelta(days=13),
        due_date=today + timedelta(days=1),
        returned_at=None,
    )
    db.add_all([l_today, l_yesterday, l_tomorrow])
    db.flush()
    id_today = l_today.id
    id_yesterday = l_yesterday.id
    id_tomorrow = l_tomorrow.id

    r_today = client.get(f"/api/loans/{id_today}").json()
    assert r_today["status"] == "active"
    assert r_today["is_overdue"] is False

    r_yesterday = client.get(f"/api/loans/{id_yesterday}").json()
    assert r_yesterday["status"] == "overdue"
    assert r_yesterday["is_overdue"] is True

    r_tomorrow = client.get(f"/api/loans/{id_tomorrow}").json()
    assert r_tomorrow["status"] == "active"
    assert r_tomorrow["is_overdue"] is False


# ── 5. Privacy & Loan Queries ─────────────────────────────────────────────────

def test_student_accesses_only_own_loans(client, auth_librarian, auth_student, auth_student_two, seed_circulation_data):
    """
    Verifies that:
    1. /api/loans/me returns only the authenticated student's loans.
    2. Student 1 cannot view Student 2's loan details (403 Forbidden).
    3. Librarian can view any loan detail.
    """
    headers_lib = auth_librarian["headers"]

    # Issue loan to student 1
    r1 = client.post(
        "/api/loans",
        json={"student_id": auth_student["user_id"], "copy_id": seed_circulation_data["c_avail1_id"]},
        headers=headers_lib,
    )
    loan1_id = r1.json()["id"]

    # Issue loan to student 2
    r2 = client.post(
        "/api/loans",
        json={"student_id": auth_student_two["user_id"], "copy_id": seed_circulation_data["c_avail2_id"]},
        headers=headers_lib,
    )
    loan2_id = r2.json()["id"]

    # Switch client session to Student 1
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    # Student 1 lists my-loans
    my_loans = client.get("/api/loans/me").json()
    assert my_loans["total"] == 1
    assert my_loans["items"][0]["id"] == loan1_id

    # Student 1 can view own loan detail
    r_own = client.get(f"/api/loans/{loan1_id}")
    assert r_own.status_code == 200
    assert r_own.json()["id"] == loan1_id

    # Student 1 FORBIDDEN from viewing Student 2's loan detail
    r_other = client.get(f"/api/loans/{loan2_id}")
    assert r_other.status_code == 403

    # Librarian can view both loans
    client.cookies.set("access_token", create_access_token(auth_librarian["user_id"], role="librarian"))
    client.cookies.set("csrf_token", "lib-view-token")
    assert client.get(f"/api/loans/{loan1_id}").status_code == 200
    assert client.get(f"/api/loans/{loan2_id}").status_code == 200


def test_librarian_listing_and_filtering(client, auth_librarian, auth_student, auth_student_two, seed_circulation_data):
    """
    Librarian listing of loans supports pagination and filtering by:
    - student_id
    - copy_id
    - book_id
    - status ('active', 'returned')
    """
    headers = auth_librarian["headers"]

    # Create 2 loans
    r1 = client.post("/api/loans", json={"student_id": auth_student["user_id"], "copy_id": seed_circulation_data["c_avail1_id"]}, headers=headers)
    loan1_id = r1.json()["id"]

    r2 = client.post("/api/loans", json={"student_id": auth_student_two["user_id"], "copy_id": seed_circulation_data["c_avail2_id"]}, headers=headers)
    loan2_id = r2.json()["id"]

    # Return loan 1
    client.post(f"/api/loans/{loan1_id}/return", headers=headers)

    # Filter by student_id
    r_stud = client.get(f"/api/loans?student_id={auth_student['user_id']}", headers=headers).json()
    assert r_stud["total"] == 1
    assert r_stud["items"][0]["id"] == loan1_id

    # Filter by copy_id
    r_copy = client.get(f"/api/loans?copy_id={seed_circulation_data['c_avail2_id']}", headers=headers).json()
    assert r_copy["total"] == 1
    assert r_copy["items"][0]["id"] == loan2_id

    # Filter by book_id
    r_book = client.get(f"/api/loans?book_id={seed_circulation_data['book_active_id']}", headers=headers).json()
    assert r_book["total"] == 2

    # Filter by status: active
    r_active = client.get("/api/loans?status=active", headers=headers).json()
    assert all(l["status"] == "active" for l in r_active["items"])

    # Filter by status: returned
    r_returned = client.get("/api/loans?status=returned", headers=headers).json()
    assert all(l["status"] == "returned" for l in r_returned["items"])


# ── 6. Dynamic Inventory Counts Reflection ────────────────────────────────────

def test_inventory_counts_reflect_issue_and_return(client, auth_librarian, auth_student, seed_circulation_data):
    """
    Verifies that:
    1. Initial book detail shows available_copies matching physical available count.
    2. Issuing a copy decrements available_copies by 1; total_copies unchanged.
    3. Returning the copy increments available_copies back.
    4. If copy was moved to 'maintenance' while loaned, returning it does NOT increase available_copies.
    """
    headers = auth_librarian["headers"]
    book_id = seed_circulation_data["book_active_id"]
    copy_id = seed_circulation_data["c_avail1_id"]

    # Initial available count
    init_book = client.get(f"/api/books/{book_id}").json()
    initial_avail = init_book["available_copies"]
    initial_total = init_book["total_copies"]

    # 1. Issue copy
    client.post("/api/loans", json={"student_id": auth_student["user_id"], "copy_id": copy_id}, headers=headers)

    book_after_issue = client.get(f"/api/books/{book_id}").json()
    assert book_after_issue["available_copies"] == initial_avail - 1
    assert book_after_issue["total_copies"] == initial_total

    # 2. Return copy
    active_loan_id = client.get(f"/api/loans?copy_id={copy_id}&status=active", headers=headers).json()["items"][0]["id"]
    client.post(f"/api/loans/{active_loan_id}/return", headers=headers)

    book_after_return = client.get(f"/api/books/{book_id}").json()
    assert book_after_return["available_copies"] == initial_avail

    # 3. Issue again, update copy to maintenance, then return
    client.post("/api/loans", json={"student_id": auth_student["user_id"], "copy_id": copy_id}, headers=headers)
    new_loan_id = client.get(f"/api/loans?copy_id={copy_id}&status=active", headers=headers).json()["items"][0]["id"]

    # Set operational_status to maintenance while out
    client.patch(f"/api/copies/{copy_id}", json={"operational_status": "maintenance"}, headers=headers)

    # Return loan
    client.post(f"/api/loans/{new_loan_id}/return", headers=headers)

    # Count must NOT include the maintenance copy in available_copies
    book_after_maint_return = client.get(f"/api/books/{book_id}").json()
    assert book_after_maint_return["available_copies"] == initial_avail - 1


# ── 7. Transaction Rollback on Failure ─────────────────────────────────────────

def test_failed_issue_leaves_no_orphan_records(client, auth_librarian, auth_student, seed_circulation_data, db: Session):
    """
    If loan creation fails due to a validation or database error,
    no partial or dirty records are committed.
    """
    headers = auth_librarian["headers"]
    init_loans_count = len(db.execute(select(Loan)).scalars().all())

    # Invalid student
    client.post("/api/loans", json={"student_id": 999999, "copy_id": seed_circulation_data["c_avail1_id"]}, headers=headers)

    # Invalid copy
    client.post("/api/loans", json={"student_id": auth_student["user_id"], "copy_id": 999999}, headers=headers)

    post_loans_count = len(db.execute(select(Loan)).scalars().all())
    assert post_loans_count == init_loans_count


# ── 8. Concurrency Tests ──────────────────────────────────────────────────────

def test_concurrent_issue_same_copy_file_backed(tmp_path: Path):
    """
    Simulates concurrent worker threads attempting to issue the same physical copy.
    Verifies that SQLite BEGIN IMMEDIATE & uix_one_active_loan_per_copy ensures:
    - Exactly ONE request succeeds (201).
    - Competing request is serialized or rejected with 409 Conflict.
    - Exactly one active loan exists in the database.
    """
    db_file = tmp_path / "concurrent_circ.db"
    db_url = f"sqlite:///{db_file}"
    init_db(database_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    setup_engine_events(engine)

    # Seed data
    with Session(bind=engine) as s:
        with atomic_write(s):
            lib = User(email="l@test.org", full_name="L", hashed_password=hash_password("P!"), role="librarian")
            s1 = User(email="s1@test.org", full_name="S1", hashed_password=hash_password("P!"), role="student")
            s2 = User(email="s2@test.org", full_name="S2", hashed_password=hash_password("P!"), role="student")
            b = Book(title="Concurrency", author="A", category="Tech")
            s.add_all([lib, s1, s2, b])
            s.flush()
            c = BookCopy(book_id=b.id, copy_code="CONC-001", operational_status="available")
            s.add(c)
            s.flush()
            lib_id, s1_id, s2_id, copy_id = lib.id, s1.id, s2.id, c.id

    results = []
    errors = []

    def worker(student_id):
        with Session(bind=engine) as session:
            try:
                res = loans_service.issue_loan_service(
                    db=session,
                    issue_in=LoanIssueRequest(student_id=student_id, copy_id=copy_id),
                    librarian_id=lib_id,
                )
                session.commit()
                results.append(res)
            except Exception as e:
                session.rollback()
                errors.append(e)

    t1 = threading.Thread(target=worker, args=(s1_id,))
    t2 = threading.Thread(target=worker, args=(s2_id,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly 1 success, 1 failure
    assert len(results) == 1, f"Expected exactly 1 successful loan, got {len(results)}"
    assert len(errors) == 1, f"Expected exactly 1 rejected loan, got {len(errors)}"

    # Check database state
    with Session(bind=engine) as session:
        active_loans = session.execute(
            select(Loan).where(Loan.copy_id == copy_id, Loan.returned_at.is_(None))
        ).scalars().all()
        assert len(active_loans) == 1

    engine.dispose()


def test_concurrent_race_for_third_loan_slot(tmp_path: Path):
    """
    Simulates concurrent requests competing for a student's final (3rd) borrowing slot
    when the student currently has 2 active loans.
    Verifies that the student never exceeds the maximum borrowing limit of 3.
    """
    db_file = tmp_path / "concurrent_slot.db"
    db_url = f"sqlite:///{db_file}"
    init_db(database_url=db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    setup_engine_events(engine)

    with Session(bind=engine) as s:
        with atomic_write(s):
            lib = User(email="lib_slot@test.org", full_name="L", hashed_password=hash_password("P!"), role="librarian")
            student = User(email="stud_slot@test.org", full_name="S", hashed_password=hash_password("P!"), role="student")
            b = Book(title="Race Slot", author="A", category="Tech")
            s.add_all([lib, student, b])
            s.flush()

            # Create 4 copies
            copies = [BookCopy(book_id=b.id, copy_code=f"SLOT-{i}", operational_status="available") for i in range(1, 5)]
            s.add_all(copies)
            s.flush()

            # Seed 2 existing active loans for student (they have 1 slot left!)
            l1 = Loan(student_id=student.id, copy_id=copies[0].id, issued_by_id=lib.id, due_date=date.today() + timedelta(days=14))
            l2 = Loan(student_id=student.id, copy_id=copies[1].id, issued_by_id=lib.id, due_date=date.today() + timedelta(days=14))
            s.add_all([l1, l2])
            s.flush()

            lib_id = lib.id
            stud_id = student.id
            copy_3_id = copies[2].id
            copy_4_id = copies[3].id

    successes = []
    failures = []

    def worker(copy_id):
        with Session(bind=engine) as session:
            try:
                res = loans_service.issue_loan_service(
                    db=session,
                    issue_in=LoanIssueRequest(student_id=stud_id, copy_id=copy_id),
                    librarian_id=lib_id,
                )
                session.commit()
                successes.append(res)
            except Exception as e:
                session.rollback()
                failures.append(e)

    t1 = threading.Thread(target=worker, args=(copy_3_id,))
    t2 = threading.Thread(target=worker, args=(copy_4_id,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly 1 thread successfully secures the 3rd slot, the other is rejected
    assert len(successes) == 1, f"Expected exactly 1 successful loan for 3rd slot, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure when reaching 3-loan limit, got {len(failures)}"

    # In database, total active loans for student must be exactly 3
    with Session(bind=engine) as session:
        active_count = session.execute(
            select(Loan).where(Loan.student_id == stud_id, Loan.returned_at.is_(None))
        ).scalars().all()
        assert len(active_count) == 3

    engine.dispose()


def test_loan_status_filter_exact_agreement(client, auth_librarian, auth_student, seed_circulation_data, db: Session):
    """
    Regression test verifying exact agreement between status filtering and dynamic serialized status:
    1. Active loan due today (due_date == today, returned_at is None)
       -> Appears in status=active, NOT in status=overdue, NOT in status=returned
    2. Overdue loan due yesterday (due_date == today - 1 day, returned_at is None)
       -> Appears in status=overdue, NOT in status=active, NOT in status=returned
    3. Returned loan (returned_at is not None)
       -> Appears in status=returned, NOT in status=active, NOT in status=overdue
    """
    today = date.today()
    stud_id = auth_student["user_id"]
    lib_id = auth_librarian["user_id"]

    # 1. Active loan due today
    loan_active = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail1_id"],
        issued_by_id=lib_id,
        issued_at=datetime.utcnow() - timedelta(days=14),
        due_date=today,
        returned_at=None,
    )
    # 2. Overdue loan due yesterday
    loan_overdue = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail2_id"],
        issued_by_id=lib_id,
        issued_at=datetime.utcnow() - timedelta(days=15),
        due_date=today - timedelta(days=1),
        returned_at=None,
    )
    # 3. Returned loan
    loan_returned = Loan(
        student_id=stud_id,
        copy_id=seed_circulation_data["c_avail3_id"],
        issued_by_id=lib_id,
        issued_at=datetime.utcnow() - timedelta(days=10),
        due_date=today + timedelta(days=4),
        returned_at=datetime.utcnow() - timedelta(days=1),
    )
    db.add_all([loan_active, loan_overdue, loan_returned])
    db.flush()

    active_id = loan_active.id
    overdue_id = loan_overdue.id
    returned_id = loan_returned.id
    headers = auth_librarian["headers"]

    # Filter status=active
    resp_active = client.get("/api/loans?status=active", headers=headers).json()
    active_ids = [l["id"] for l in resp_active["items"]]
    assert active_id in active_ids
    assert overdue_id not in active_ids
    assert returned_id not in active_ids
    for item in resp_active["items"]:
        assert item["status"] == "active"
        assert item["is_overdue"] is False
        assert item["returned_at"] is None

    # Filter status=overdue
    resp_overdue = client.get("/api/loans?status=overdue", headers=headers).json()
    overdue_ids = [l["id"] for l in resp_overdue["items"]]
    assert overdue_id in overdue_ids
    assert active_id not in overdue_ids
    assert returned_id not in overdue_ids
    for item in resp_overdue["items"]:
        assert item["status"] == "overdue"
        assert item["is_overdue"] is True
        assert item["returned_at"] is None

    # Filter status=returned
    resp_returned = client.get("/api/loans?status=returned", headers=headers).json()
    returned_ids = [l["id"] for l in resp_returned["items"]]
    assert returned_id in returned_ids
    assert active_id not in returned_ids
    assert overdue_id not in returned_ids
    for item in resp_returned["items"]:
        assert item["status"] == "returned"
        assert item["is_overdue"] is False
        assert item["returned_at"] is not None

    # Student /api/loans/me filtering
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf_val"])

    stud_active = client.get("/api/loans/me?status=active").json()
    assert [l["id"] for l in stud_active["items"]] == [active_id]

    stud_overdue = client.get("/api/loans/me?status=overdue").json()
    assert [l["id"] for l in stud_overdue["items"]] == [overdue_id]

    stud_returned = client.get("/api/loans/me?status=returned").json()
    assert [l["id"] for l in stud_returned["items"]] == [returned_id]
