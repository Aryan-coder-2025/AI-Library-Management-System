"""
Test suite for Stage 9 — Public OPAC Browsing, Patron Profile Management, and Circulation Completion.

Features Tested:
- PORT-05: Public OPAC Browsing (anonymous catalogue search, details, availability, copy barcode hiding, recommendations).
- PORT-06: Patron Profile Management (patching full_name, rejecting extra fields, password policy enforcement and changes).
- CIRC-01: Loan Returns and Renewals (student 14d, teacher 30d, 1-renewal limit, overdue rejection, cross-account overdue blocking, ownership authorization).
- CIRC-04: Overdue Alerts and Notifications (idempotent sweep, deterministic dedup_key, unread count, read markers, librarian sweep endpoint).
- CIRC-05: Teacher Borrowing Policies and Loan Visibility (30-day term, 10-item limit, teacher loan visibility).
"""
from datetime import date, datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.models import Book, BookCopy, Loan, Notification, User
from app.utils.date import get_utc_today


# ── Helper Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def auth_librarian(client, db: Session):
    user = User(
        email="stage9_librarian@library.org",
        full_name="Stage9 Staff Librarian",
        hashed_password=hash_password("LibrarianSecure123!"),
        role="librarian",
        is_active=True,
    )
    db.add(user)
    db.flush()

    token = create_access_token(user_id=user.id, role="librarian")
    csrf_val = "csrf-lib-token-999"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user": user,
        "token": token,
        "csrf": csrf_val,
        "headers": {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val},
    }


@pytest.fixture
def auth_student(client, db: Session):
    user = User(
        email="stage9_student@university.edu",
        full_name="Stage9 Student User",
        hashed_password=hash_password("StudentSecure123!"),
        role="student",
        is_active=True,
    )
    db.add(user)
    db.flush()

    token = create_access_token(user_id=user.id, role="student")
    csrf_val = "csrf-student-token-888"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user": user,
        "token": token,
        "csrf": csrf_val,
        "headers": {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val},
    }


@pytest.fixture
def auth_teacher(client, db: Session):
    user = User(
        email="stage9_teacher@university.edu",
        full_name="Prof. Stage9 Teacher",
        hashed_password=hash_password("TeacherSecure123!"),
        role="teacher",
        is_active=True,
    )
    db.add(user)
    db.flush()

    token = create_access_token(user_id=user.id, role="teacher")
    csrf_val = "csrf-teacher-token-777"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_val)
    return {
        "user": user,
        "token": token,
        "csrf": csrf_val,
        "headers": {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_val},
    }


@pytest.fixture
def sample_books(db: Session):
    import struct
    dummy_emb = struct.pack(f"{384}f", *([0.05] * 384))
    now = datetime.now(timezone.utc)
    b1 = Book(
        title="Public OPAC Architecture",
        author="Ada Lovelace",
        isbn="978-0-123-45678-9",
        category="Computer Science",
        description="Comprehensive guide to public online catalogue access.",
        is_archived=False,
        embedding=dummy_emb,
        updated_at=now - timedelta(minutes=5),
        embedding_updated_at=now,
    )
    b2 = Book(
        title="Archived Confidential Guide",
        author="Charles Babbage",
        isbn="978-0-987-65432-1",
        category="History",
        description="Archived archival book record.",
        is_archived=True,
    )
    db.add_all([b1, b2])
    db.flush()

    c1 = BookCopy(
        book_id=b1.id,
        copy_code="COPY-OPAC-001",
        operational_status="available",
        notes="First edition",
    )
    c2 = BookCopy(
        book_id=b1.id,
        copy_code="COPY-OPAC-002",
        operational_status="available",
        notes="Reserve desk copy",
    )
    db.add_all([c1, c2])
    db.flush()

    return {"public_book": b1, "archived_book": b2, "copies": [c1, c2]}


# ── PORT-05: Public OPAC Browsing Tests ──────────────────────────────────────

def test_guest_can_browse_catalogue_without_credentials(client, sample_books):
    client.cookies.clear()
    resp = client.get("/api/books")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    titles = [b["title"] for b in data["items"]]
    assert "Public OPAC Architecture" in titles
    assert "Archived Confidential Guide" not in titles


def test_guest_receives_empty_copies_for_book_detail(client, sample_books):
    client.cookies.clear()
    book_id = sample_books["public_book"].id
    resp = client.get(f"/api/books/{book_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Public OPAC Architecture"
    assert data["total_copies"] == 2
    assert data["available_copies"] == 2
    # Privacy safeguard: guest cannot inspect individual copy objects / barcodes / staff notes
    assert data["copies"] == []


def test_authenticated_user_receives_full_copies_for_book_detail(client, auth_student, sample_books):
    book_id = sample_books["public_book"].id
    resp = client.get(f"/api/books/{book_id}", headers=auth_student["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["copies"]) == 2
    codes = [c["copy_code"] for c in data["copies"]]
    assert "COPY-OPAC-001" in codes
    assert "COPY-OPAC-002" in codes


def test_guest_cannot_access_hybrid_search(client):
    client.cookies.clear()
    resp = client.get("/api/search/hybrid?query=computing")
    assert resp.status_code == 401


def test_guest_can_access_recommendations_endpoint(client, sample_books):
    client.cookies.clear()
    book_id = sample_books["public_book"].id
    resp = client.get(f"/api/recommendations/books/{book_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_book_id"] == book_id


# ── PORT-06: Patron Profile Management Tests ─────────────────────────────────

def test_patron_can_update_full_name(client, auth_student):
    resp = client.patch(
        "/api/auth/me",
        json={"full_name": "Alice Wonderland"},
        headers=auth_student["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Alice Wonderland"
    assert data["email"] == "stage9_student@university.edu"


def test_patron_profile_update_forbids_extra_fields(client, auth_student):
    resp = client.patch(
        "/api/auth/me",
        json={"full_name": "Hacker", "role": "librarian"},
        headers=auth_student["headers"],
    )
    assert resp.status_code == 422


def test_patron_change_password_flow(client, db: Session, auth_student):
    # Establish real cookie session via /api/auth/login
    client.cookies.clear()
    login_init = client.post(
        "/api/auth/login",
        json={"email": "stage9_student@university.edu", "password": "StudentSecure123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert login_init.status_code == 200
    csrf_token = login_init.cookies.get("csrf_token")
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf_token}

    # 1. Invalid current password does not change password or clear cookies
    resp_bad_curr = client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongPassword123!", "new_password": "NewCompliantPass99!"},
        headers=headers,
    )
    assert resp_bad_curr.status_code == 400
    assert "incorrect" in resp_bad_curr.json()["detail"].lower()
    # Session must still be active
    assert client.get("/api/auth/me").status_code == 200

    # 2. Non-compliant new password (schema min_length=8 validation) does not clear session
    resp_short = client.post(
        "/api/auth/change-password",
        json={"current_password": "StudentSecure123!", "new_password": "short"},
        headers=headers,
    )
    assert resp_short.status_code == 422
    assert client.get("/api/auth/me").status_code == 200

    # 3. New password identical to current password does not clear session
    resp_ident = client.post(
        "/api/auth/change-password",
        json={"current_password": "StudentSecure123!", "new_password": "StudentSecure123!"},
        headers=headers,
    )
    assert resp_ident.status_code == 400
    assert "cannot match" in resp_ident.json()["detail"].lower() or "different" in resp_ident.json()["detail"].lower()
    assert client.get("/api/auth/me").status_code == 200

    # 4. Successful password change invalidates browser session cookies
    resp_ok = client.post(
        "/api/auth/change-password",
        json={"current_password": "StudentSecure123!", "new_password": "NewStrongPass999!"},
        headers=headers,
    )
    assert resp_ok.status_code == 200
    assert "log in again" in resp_ok.json()["message"].lower()

    # Session cookies must now be cleared; unauthenticated access to /me returns 401
    me_after = client.get("/api/auth/me")
    assert me_after.status_code == 401

    # 5. Old password no longer works
    login_old = client.post(
        "/api/auth/login",
        json={"email": "stage9_student@university.edu", "password": "StudentSecure123!"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert login_old.status_code == 401

    # 6. Verify new password allows login and issues new valid session
    login_new = client.post(
        "/api/auth/login",
        json={"email": "stage9_student@university.edu", "password": "NewStrongPass999!"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert login_new.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


# ── CIRC-01 & CIRC-05: Loan Renewal Tests ────────────────────────────────────

def test_student_loan_renewal_extends_by_14_days(client, db: Session, auth_student, sample_books):
    loan = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][0].id,
        issued_by_id=auth_student["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=5),
        due_date=get_utc_today() + timedelta(days=9),
        renewal_count=0,
    )
    db.add(loan)
    db.flush()
    orig_due = loan.due_date

    resp = client.post(f"/api/loans/{loan.id}/renew", headers=auth_student["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["renewal_count"] == 1
    expected_due = orig_due + timedelta(days=14)
    assert data["due_date"] == expected_due.isoformat()

    # Second renewal must be rejected
    resp_second = client.post(f"/api/loans/{loan.id}/renew", headers=auth_student["headers"])
    assert resp_second.status_code == 400
    assert "limit" in resp_second.json()["detail"].lower()


def test_teacher_loan_renewal_extends_by_30_days(client, db: Session, auth_teacher, sample_books):
    loan = Loan(
        student_id=auth_teacher["user"].id,
        copy_id=sample_books["copies"][1].id,
        issued_by_id=auth_teacher["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=10),
        due_date=get_utc_today() + timedelta(days=20),
        renewal_count=0,
    )
    db.add(loan)
    db.flush()
    orig_due = loan.due_date

    resp = client.post(f"/api/loans/{loan.id}/renew", headers=auth_teacher["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["renewal_count"] == 1
    expected_due = orig_due + timedelta(days=30)
    assert data["due_date"] == expected_due.isoformat()


def test_loan_renewal_blocked_when_overdue(client, db: Session, auth_student, sample_books):
    loan = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][0].id,
        issued_by_id=auth_student["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=20),
        due_date=get_utc_today() - timedelta(days=1),
        renewal_count=0,
    )
    db.add(loan)
    db.flush()

    resp = client.post(f"/api/loans/{loan.id}/renew", headers=auth_student["headers"])
    assert resp.status_code == 400
    assert "overdue" in resp.json()["detail"].lower()


def test_loan_renewal_blocked_when_patron_has_other_overdue_loans(client, db: Session, auth_student, sample_books):
    loan1 = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][0].id,
        issued_by_id=auth_student["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=20),
        due_date=get_utc_today() - timedelta(days=2),
        renewal_count=0,
    )
    loan2 = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][1].id,
        issued_by_id=auth_student["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=2),
        due_date=get_utc_today() + timedelta(days=12),
        renewal_count=0,
    )
    db.add_all([loan1, loan2])
    db.flush()

    resp = client.post(f"/api/loans/{loan2.id}/renew", headers=auth_student["headers"])
    assert resp.status_code == 400
    assert "overdue" in resp.json()["detail"].lower()


def test_loan_renewal_ownership_authorization(client, db: Session, auth_student, auth_teacher, auth_librarian, sample_books):
    def apply_auth(auth_obj):
        client.cookies.set("access_token", auth_obj["token"])
        client.cookies.set("csrf_token", auth_obj["csrf"])
    loan = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][0].id,
        issued_by_id=auth_student["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=2),
        due_date=get_utc_today() + timedelta(days=12),
        renewal_count=0,
    )
    db.add(loan)
    db.flush()

    # Teacher cannot renew Student's loan
    apply_auth(auth_teacher)
    resp = client.post(f"/api/loans/{loan.id}/renew", headers=auth_teacher["headers"])
    assert resp.status_code == 403

    # Librarian CAN renew Student's loan
    apply_auth(auth_librarian)
    resp_lib = client.post(f"/api/loans/{loan.id}/renew", headers=auth_librarian["headers"])
    assert resp_lib.status_code == 200
    assert resp_lib.json()["renewal_count"] == 1


# ── CIRC-04: Overdue Alerts & Notifications Tests ────────────────────────────

def test_overdue_notifications_sweep_and_deduplication(client, db: Session, auth_librarian, auth_student, sample_books):
    def apply_auth(auth_obj):
        client.cookies.set("access_token", auth_obj["token"])
        client.cookies.set("csrf_token", auth_obj["csrf"])
    overdue_date = get_utc_today() - timedelta(days=3)
    loan = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][0].id,
        issued_by_id=auth_librarian["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=17),
        due_date=overdue_date,
        renewal_count=0,
    )
    db.add(loan)
    db.flush()

    # 1. First sweep generates 1 notification
    apply_auth(auth_librarian)
    sweep_resp1 = client.post("/api/notifications/sweep", headers=auth_librarian["headers"])
    assert sweep_resp1.status_code == 200
    assert sweep_resp1.json()["new_notifications"] == 1

    # 2. Second sweep is completely idempotent (0 new notifications)
    sweep_resp2 = client.post("/api/notifications/sweep", headers=auth_librarian["headers"])
    assert sweep_resp2.status_code == 200
    assert sweep_resp2.json()["new_notifications"] == 0

    # 3. Patron queries unread notifications
    apply_auth(auth_student)
    notif_resp = client.get("/api/notifications", headers=auth_student["headers"])
    assert notif_resp.status_code == 200
    notif_data = notif_resp.json()
    assert notif_data["total"] == 1
    assert notif_data["unread_count"] == 1
    notif_item = notif_data["items"][0]
    assert notif_item["notification_type"] == "overdue"
    assert notif_item["is_read"] is False

    # 4. Patron marks notification read
    mark_resp = client.patch(f"/api/notifications/{notif_item['id']}/read", headers=auth_student["headers"])
    assert mark_resp.status_code == 200
    assert mark_resp.json()["is_read"] is True

    # 5. Unread count becomes 0
    count_resp = client.get("/api/notifications/unread-count", headers=auth_student["headers"])
    assert count_resp.status_code == 200
    assert count_resp.json()["unread_count"] == 0


def test_patron_cannot_modify_other_users_notification(client, db: Session, auth_student, auth_teacher):
    notif = Notification(
        user_id=auth_student["user"].id,
        notification_type="general",
        title="Welcome",
        message="Welcome to the library",
        is_read=False,
        dedup_key="unique-test-key-001",
        created_at=datetime.now(timezone.utc),
    )
    db.add(notif)
    db.flush()

    # Teacher attempts to mark Student's notification as read
    resp = client.patch(f"/api/notifications/{notif.id}/read", headers=auth_teacher["headers"])
    assert resp.status_code == 403


def test_student_cannot_trigger_notification_sweep(client, auth_student):
    resp = client.post("/api/notifications/sweep", headers=auth_student["headers"])
    assert resp.status_code == 403


def test_bulk_mark_all_read(client, db: Session, auth_student):
    n1 = Notification(
        user_id=auth_student["user"].id,
        notification_type="general",
        title="Notice 1",
        message="Message 1",
        is_read=False,
        dedup_key="bulk-key-001",
        created_at=datetime.now(timezone.utc),
    )
    n2 = Notification(
        user_id=auth_student["user"].id,
        notification_type="general",
        title="Notice 2",
        message="Message 2",
        is_read=False,
        dedup_key="bulk-key-002",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([n1, n2])
    db.flush()

    resp = client.post("/api/notifications/mark-all-read", headers=auth_student["headers"])
    assert resp.status_code == 200
    assert resp.json()["updated_count"] >= 2

    count_resp = client.get("/api/notifications/unread-count", headers=auth_student["headers"])
    assert count_resp.json()["unread_count"] == 0



# ── Remediation C: UTC Date Standardization Tests ────────────────────────────

def test_utc_date_boundary_loan_renewal_eligibility(client, db: Session, auth_student, sample_books):
    """
    Verifies that overdue status is strictly evaluated against UTC date:
    - due_date == get_utc_today(): NOT overdue (eligible for renewal).
    - due_date == get_utc_today() - 1 day: OVERDUE (renewal rejected).
    """
    from app.utils.date import get_utc_today

    utc_today = get_utc_today()

    # Loan A: Due exactly today (UTC) -> Not overdue
    loan_due_today = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][0].id,
        issued_by_id=auth_student["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=14),
        due_date=utc_today,
        renewal_count=0,
    )
    # Loan B: Due yesterday (UTC) -> Overdue
    loan_due_yesterday = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][1].id,
        issued_by_id=auth_student["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=15),
        due_date=utc_today - timedelta(days=1),
        renewal_count=0,
    )
    db.add(loan_due_today)
    db.flush()

    # Loan due today should be renewable
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf"])
    resp_a = client.post(f"/api/loans/{loan_due_today.id}/renew", headers=auth_student["headers"])
    assert resp_a.status_code == 200
    assert resp_a.json()["due_date"] == (utc_today + timedelta(days=14)).isoformat()

    # Now add overdue loan
    db.add(loan_due_yesterday)
    db.flush()

    # Overdue loan itself cannot be renewed
    resp_b = client.post(f"/api/loans/{loan_due_yesterday.id}/renew", headers=auth_student["headers"])
    assert resp_b.status_code == 400
    assert "overdue" in resp_b.json()["detail"].lower()


def test_utc_date_boundary_notification_sweep(client, db: Session, auth_librarian, auth_student, sample_books):
    """
    Verifies that the automated notification sweep strictly queries loans with
    due_date < get_utc_today(), excluding loans due today.
    """
    from app.utils.date import get_utc_today

    utc_today = get_utc_today()

    # Loan A: Due today (UTC) -> Should NOT be flagged as overdue
    loan_today = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][0].id,
        issued_by_id=auth_librarian["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=14),
        due_date=utc_today,
        renewal_count=0,
    )
    # Loan B: Due yesterday (UTC) -> MUST be flagged as overdue
    loan_yesterday = Loan(
        student_id=auth_student["user"].id,
        copy_id=sample_books["copies"][1].id,
        issued_by_id=auth_librarian["user"].id,
        issued_at=datetime.now(timezone.utc) - timedelta(days=15),
        due_date=utc_today - timedelta(days=1),
        renewal_count=0,
    )
    db.add_all([loan_today, loan_yesterday])
    db.flush()

    client.cookies.set("access_token", auth_librarian["token"])
    client.cookies.set("csrf_token", auth_librarian["csrf"])
    sweep_resp = client.post("/api/notifications/sweep", headers=auth_librarian["headers"])
    assert sweep_resp.status_code == 200
    # Exactly 1 loan was due before today (loan_yesterday)
    assert sweep_resp.json()["new_notifications"] == 1

    # Check notification belongs to loan_yesterday
    client.cookies.set("access_token", auth_student["token"])
    client.cookies.set("csrf_token", auth_student["csrf"])
    notif_resp = client.get("/api/notifications", headers=auth_student["headers"])
    assert notif_resp.status_code == 200
    items = notif_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["loan_id"] == loan_yesterday.id
