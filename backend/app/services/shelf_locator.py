"""
Physical book shelf micro-location and spatial layout service.
Maps catalogued monographs to exact physical library stacks coordinates:
Floor Number, Aisle, Bookcase Bay, Shelf Tier (1-5), and the exact Book Slot
Number (e.g. 7th book from left edge) according to standard Dewey Decimal Classification.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import Book, LibraryFloor
from app.schemas import (
    BookShelfLocationResponse,
    ShelfBookNeighbor,
    ShelfReadingAuditResponse,
    ExitGateVerificationResponse,
    SelfCheckoutResponse,
)


CATEGORY_STACK_MAP = {
    "Mathematics": {
        "floor_number": 1,
        "floor_name": "1st Floor — Collaborative Commons & Mathematical Sciences",
        "aisle": "Aisle 1A",
        "dewey_base": "510.0",
        "bay_prefix": "Bay",
        "x": 280.0,
        "y": 210.0,
        "normalized_x": 0.28,
        "normalized_y": 0.30,
    },
    "Physics": {
        "floor_number": 1,
        "floor_name": "1st Floor — Collaborative Commons & Mathematical Sciences",
        "aisle": "Aisle 1B",
        "dewey_base": "530.0",
        "bay_prefix": "Bay",
        "x": 280.0,
        "y": 380.0,
        "normalized_x": 0.28,
        "normalized_y": 0.54,
    },
    "Philosophy of Technology": {
        "floor_number": 1,
        "floor_name": "1st Floor — Collaborative Commons & Mathematical Sciences",
        "aisle": "Aisle 1C",
        "dewey_base": "601.0",
        "bay_prefix": "Bay",
        "x": 280.0,
        "y": 530.0,
        "normalized_x": 0.28,
        "normalized_y": 0.75,
    },
    "Computer Science": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2A",
        "dewey_base": "004.0",
        "bay_prefix": "Bay",
        "x": 450.0,
        "y": 190.0,
        "normalized_x": 0.45,
        "normalized_y": 0.27,
    },
    "Software Engineering": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2B",
        "dewey_base": "005.1",
        "bay_prefix": "Bay",
        "x": 450.0,
        "y": 330.0,
        "normalized_x": 0.45,
        "normalized_y": 0.47,
    },
    "Algorithms & Complexity": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2C",
        "dewey_base": "005.11",
        "bay_prefix": "Bay",
        "x": 450.0,
        "y": 480.0,
        "normalized_x": 0.45,
        "normalized_y": 0.68,
    },
    "Artificial Intelligence": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2D",
        "dewey_base": "006.3",
        "bay_prefix": "Bay",
        "x": 720.0,
        "y": 230.0,
        "normalized_x": 0.72,
        "normalized_y": 0.32,
    },
    "Distributed Systems": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3A",
        "dewey_base": "004.36",
        "bay_prefix": "Bay",
        "x": 340.0,
        "y": 210.0,
        "normalized_x": 0.34,
        "normalized_y": 0.30,
    },
    "Cybersecurity & Cryptography": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3B",
        "dewey_base": "005.8",
        "bay_prefix": "Bay",
        "x": 340.0,
        "y": 360.0,
        "normalized_x": 0.34,
        "normalized_y": 0.51,
    },
    "Data Science": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3C",
        "dewey_base": "005.7",
        "bay_prefix": "Bay",
        "x": 340.0,
        "y": 510.0,
        "normalized_x": 0.34,
        "normalized_y": 0.72,
    },
    "Information Systems": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3D",
        "dewey_base": "004.6",
        "bay_prefix": "Bay",
        "x": 680.0,
        "y": 250.0,
        "normalized_x": 0.68,
        "normalized_y": 0.35,
    },
    "Robotics": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3E",
        "dewey_base": "629.8",
        "bay_prefix": "Bay",
        "x": 680.0,
        "y": 420.0,
        "normalized_x": 0.68,
        "normalized_y": 0.60,
    },
}

TIER_NAMES = {
    1: "Tier 1 (Bottom Shelf — 35 cm from ground)",
    2: "Tier 2 (Lower Shelf — 70 cm from ground)",
    3: "Tier 3 (Mid-Chest Level — 105 cm from ground)",
    4: "Tier 4 (Eye Level — 140 cm from ground)",
    5: "Tier 5 (Top Shelf — 175 cm from ground)",
}


def _generate_cutter_number(author: str, title: str) -> str:
    """Generates realistic standard Cutter-Sanborn 3-character shelfmark."""
    author_clean = author.split(",")[-1].strip().split()[-1] if author else "Anon"
    first_letter = author_clean[0].upper() if author_clean else "A"
    code_sum = sum(ord(c) for c in author_clean[:4]) % 89 + 10
    work_letter = title.strip()[0].lower() if title.strip() else "x"
    return f"{first_letter}{code_sum}{work_letter}"


def locate_book_on_shelf_service(db: Session, book_id: int) -> BookShelfLocationResponse:
    """
    Computes precise micro-location coordinates for a book down to:
    Floor, Aisle, Bookcase Bay, Shelf Tier (1-5), and exact Book Slot Number from left.
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book #{book_id} not found in catalogue.",
        )

    # Determine Stack Area
    category = book.category or "Computer Science"
    stack_info = CATEGORY_STACK_MAP.get(category, CATEGORY_STACK_MAP["Computer Science"])

    # Query all non-archived books in this category sorted deterministically by title
    category_books = (
        db.query(Book)
        .filter(Book.category == category, Book.is_archived.is_(False))
        .order_by(Book.title.asc(), Book.id.asc())
        .all()
    )

    # Find position of target book within category
    try:
        k = next(i for i, b in enumerate(category_books) if b.id == book.id)
    except StopIteration:
        k = 0

    books_per_tier = 25
    tiers_per_bay = 5

    tier_idx = (k // books_per_tier) % tiers_per_bay
    shelf_tier = tier_idx + 1
    bay_idx = (k // (books_per_tier * tiers_per_bay)) + 1
    bay_name = f"{stack_info['bay_prefix']} {bay_idx:02d}"

    slot_number = (k % books_per_tier) + 1
    position_from_left = slot_number
    position_from_right = books_per_tier - slot_number + 1

    cutter = _generate_cutter_number(book.author, book.title)
    call_number = f"{stack_info['dewey_base']} {cutter}"

    # Get adjacent shelf neighbors (same tier)
    tier_start_idx = (k // books_per_tier) * books_per_tier
    tier_books = category_books[tier_start_idx : tier_start_idx + books_per_tier]

    neighbors: List[ShelfBookNeighbor] = []
    # Take a 5-book window centered on target
    local_idx = k - tier_start_idx
    window_start = max(0, local_idx - 2)
    window_end = min(len(tier_books), local_idx + 3)

    for idx in range(window_start, window_end):
        b = tier_books[idx]
        slot = idx + 1
        b_cutter = _generate_cutter_number(b.author, b.title)
        neighbors.append(
            ShelfBookNeighbor(
                slot=slot,
                book_id=b.id,
                title=b.title,
                author=b.author,
                call_number=f"{stack_info['dewey_base']} {b_cutter}",
                is_target=(b.id == book.id),
            )
        )

    tier_name = TIER_NAMES.get(shelf_tier, f"Tier {shelf_tier}")

    turn_by_turn = [
        f"1. Enter via Central Library Atrium on Ground Floor.",
        f"2. Take central stairs or elevator to {stack_info['floor_name']}.",
        f"3. Proceed along the main circulation corridor into {stack_info['aisle']} ({category}).",
        f"4. Walk up to Bookcase {bay_name}.",
        f"5. Look at {tier_name} ({shelf_tier} of 5 shelves).",
        f"6. Count {position_from_left} books from the LEFT edge — '{book.title}' is sitting at Slot #{position_from_left}.",
    ]

    guidance = (
        f"Located on {stack_info['floor_name']} in {stack_info['aisle']}, {bay_name}, "
        f"{tier_name}. Book #{position_from_left} from the LEFT edge (Call #: {call_number})."
    )

    return BookShelfLocationResponse(
        book_id=book.id,
        title=book.title,
        author=book.author,
        category=category,
        call_number=call_number,
        floor_number=stack_info["floor_number"],
        floor_name=stack_info["floor_name"],
        aisle=stack_info["aisle"],
        bay=bay_name,
        shelf_tier=shelf_tier,
        shelf_tier_name=tier_name,
        total_tiers=tiers_per_bay,
        slot_number=slot_number,
        position_from_left=position_from_left,
        position_from_right=position_from_right,
        direction="Left to Right",
        shelf_capacity=books_per_tier,
        turn_by_turn_directions=turn_by_turn,
        guidance=guidance,
        map_coordinates={
            "x": stack_info["x"],
            "y": stack_info["y"],
            "normalized_x": stack_info["normalized_x"],
            "normalized_y": stack_info["normalized_y"],
        },
        shelf_neighbors=neighbors,
    )


def report_book_missing_service(
    db: Session,
    book_id: int,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, str]:
    """
    Logs an audit event and temporarily flags an available copy for staff shelf inspection,
    eliminating 'ghost availability' and updating staff audit logs.
    """
    from app.database import atomic_write
    from app.models import BookCopy, Loan, InventoryEvent

    with atomic_write(db):
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book #{book_id} not found in catalogue.",
            )

        copies = db.query(BookCopy).filter(
            BookCopy.book_id == book_id,
            BookCopy.operational_status == "available",
        ).all()

        active_loans = db.query(Loan.copy_id).filter(Loan.returned_at.is_(None)).all()
        active_loan_ids = {l[0] for l in active_loans}

        target_copy = next((c for c in copies if c.id not in active_loan_ids), None)
        if target_copy:
            prev_status = target_copy.operational_status
            target_copy.operational_status = "maintenance"
            target_copy.notes = f"Flagged by patron for physical shelf verification: {notes or 'Reported missing from tier/slot'}"

            from app.models import User
            auditor = None
            if user_id:
                auditor = db.query(User).filter(User.id == user_id).first()
            if not auditor:
                auditor = db.query(User).first()

            if auditor:
                event = InventoryEvent(
                    copy_id=target_copy.id,
                    auditor_id=auditor.id,
                    event_type="shelf_check",
                    previous_status=prev_status,
                    new_status="maintenance",
                    notes=f"Patron missing shelf report: {notes or 'Not found at expected micro-location'}",
                )
                db.add(event)

        return {
            "message": f"Shelf audit report logged for '{book.title}'. Physical copy status marked for staff inspection to prevent ghost availability."
        }


def perform_shelf_reading_audit_service(
    db: Session,
    audited_aisle: str,
    barcode: str,
    auditor_id: Optional[int] = None,
) -> ShelfReadingAuditResponse:
    """
    Performs real-time shelf reading audit along a library aisle.
    Detects if a book is misplaced, verified in place, or a recovered missing item.
    """
    from app.database import atomic_write
    from app.models import Book, BookCopy, InventoryEvent, User

    clean_code = barcode.strip()

    # Match copy_code first
    copy = db.query(BookCopy).filter(BookCopy.copy_code == clean_code).first()

    # Match ISBN or partial copy code if not found directly
    if not copy:
        clean_isbn = clean_code.replace("-", "").replace(" ", "")
        book_match = db.query(Book).filter(Book.isbn == clean_isbn).first()
        if book_match:
            copy = db.query(BookCopy).filter(BookCopy.book_id == book_match.id).first()

    if not copy:
        copy = db.query(BookCopy).filter(BookCopy.copy_code.ilike(f"%{clean_code}%")).first()

    if not copy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No monograph copy matching barcode '{clean_code}' was found in library records.",
        )

    book = db.query(Book).filter(Book.id == copy.book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent monograph record for copy '{copy.copy_code}' not found.",
        )

    loc = locate_book_on_shelf_service(db, book.id)
    expected_aisle = loc.aisle
    was_flagged = copy.operational_status in ("maintenance", "lost")

    with atomic_write(db):
        auditor = None
        if auditor_id:
            auditor = db.query(User).filter(User.id == auditor_id).first()
        if not auditor:
            auditor = db.query(User).first()
        if not auditor:
            auditor = User(
                email="system_audit@athenaeum.edu",
                full_name="System Inventory Auditor",
                hashed_password="!",
                role="librarian",
                is_active=True,
            )
            db.add(auditor)
            db.flush()

        auditor_id_val = auditor.id
        is_correct_aisle = (audited_aisle.strip().lower() == expected_aisle.strip().lower())
        event = None

        if not is_correct_aisle:
            status_code = "misplaced"
            floor_short = loc.floor_name.split("—")[0].strip() if "—" in loc.floor_name else f"Floor {loc.floor_number}"
            action_suggested = f"Route to Reshelving Cart -> Transfer to {expected_aisle} ({floor_short})"
            msg = (
                f"🚨 MISPLACED MONOGRAPH DETECTED! '{book.title}' ({copy.copy_code}) found in {audited_aisle}, "
                f"but belongs in {expected_aisle}, {loc.bay}, {loc.shelf_tier_name}, Slot #{loc.slot_number}."
            )
            event = InventoryEvent(
                copy_id=copy.id,
                auditor_id=auditor_id_val,
                event_type="shelf_audit_misplaced",
                previous_status=copy.operational_status,
                new_status=copy.operational_status,
                notes=f"Misplaced in {audited_aisle}; belongs in {expected_aisle}",
            )
            db.add(event)
        elif was_flagged:
            status_code = "recovered"
            action_suggested = f"Restore to Active Stacks (Slot #{loc.slot_number})"
            msg = (
                f"🎉 PREVIOUSLY MISSING ITEM RECOVERED! '{book.title}' ({copy.copy_code}) verified on {audited_aisle}. "
                f"Status restored to available inventory."
            )
            prev = copy.operational_status
            copy.operational_status = "available"
            copy.notes = "Recovered during aisle shelf reading."
            event = InventoryEvent(
                copy_id=copy.id,
                auditor_id=auditor_id_val,
                event_type="shelf_audit_recovered",
                previous_status=prev,
                new_status="available",
                notes=f"Found and verified on {audited_aisle} during staff shelf audit.",
            )
            db.add(event)
        else:
            status_code = "verified_in_place"
            action_suggested = "None (Item in Correct Shelf Location)"
            msg = (
                f"✅ VERIFIED IN PLACE: '{book.title}' ({copy.copy_code}) correctly shelved on {expected_aisle}, "
                f"{loc.shelf_tier_name}, Slot #{loc.slot_number}."
            )
            event = InventoryEvent(
                copy_id=copy.id,
                auditor_id=auditor_id_val,
                event_type="shelf_audit_verified",
                previous_status=copy.operational_status,
                new_status=copy.operational_status,
                notes=f"Verified in place on {audited_aisle} (Bay {loc.bay}, Slot #{loc.slot_number}).",
            )
            db.add(event)

    return ShelfReadingAuditResponse(
        status=status_code,
        copy_code=copy.copy_code,
        book_title=book.title,
        book_id=book.id,
        category=book.category,
        dewey_call_number=loc.call_number,
        audited_aisle=audited_aisle,
        expected_floor=loc.floor_number,
        expected_aisle=loc.aisle,
        expected_bay=loc.bay,
        expected_tier=loc.shelf_tier_name,
        expected_slot=loc.slot_number,
        action_suggested=action_suggested,
        message=msg,
        audit_event_id=event.id if event else None,
    )


def execute_reshelve_action_service(
    db: Session,
    copy_code: str,
    action: str = "route_to_cart",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Handles physical reshelving buffer transitions:
    - 'route_to_cart': marks copy as 'in_reshelving' on mobile cart.
    - 'mark_on_shelf': verifies book placed back into its designated shelf slot, marking 'available'.
    """
    from app.database import atomic_write
    from app.models import BookCopy, InventoryEvent, User

    with atomic_write(db):
        copy = db.query(BookCopy).filter(BookCopy.copy_code == copy_code.strip()).first()
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book copy '{copy_code}' not found.",
            )

        auditor = db.query(User).filter(User.id == user_id).first() if user_id else db.query(User).first()
        if not auditor:
            auditor = User(
                email="system_audit@athenaeum.edu",
                full_name="System Inventory Auditor",
                hashed_password="!",
                role="librarian",
                is_active=True,
            )
            db.add(auditor)
            db.flush()
        auditor_id_val = auditor.id
        prev_status = copy.operational_status

        if action == "route_to_cart":
            copy.operational_status = "in_reshelving"
            copy.notes = "Placed on mobile reshelving cart for redistribution."
            new_status = "in_reshelving"
            event_type = "reshelving_cart_load"
            msg = f"Item {copy.copy_code} loaded onto Circulation Reshelving Cart #1."
        else:
            copy.operational_status = "available"
            copy.notes = "Verified returned to home shelf slot."
            new_status = "available"
            event_type = "reshelving_completed"
            msg = f"Item {copy.copy_code} verified returned to designated shelf tier."

        event = InventoryEvent(
            copy_id=copy.id,
            auditor_id=auditor_id_val,
            event_type=event_type,
            previous_status=prev_status,
            new_status=new_status,
            notes=msg,
        )
        db.add(event)

    return {
        "copy_code": copy.copy_code,
        "operational_status": copy.operational_status,
        "message": msg,
    }


def verify_exit_gate_service(
    db: Session,
    copy_code: str,
) -> ExitGateVerificationResponse:
    """
    Simulates physical RFID / Acousto-Magnetic security pedestals at library exits.
    Validates if an item passing the gate has an active unreturned loan.
    """
    from datetime import datetime
    from app.models import BookCopy, Book, Loan, User, InventoryEvent
    from app.database import atomic_write

    clean_code = copy_code.strip()
    copy = db.query(BookCopy).filter(BookCopy.copy_code == clean_code).first()
    if not copy:
        clean_isbn = clean_code.replace("-", "").replace(" ", "")
        book = db.query(Book).filter(Book.isbn == clean_isbn).first()
        if book:
            copy = db.query(BookCopy).filter(BookCopy.book_id == book.id).first()

    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not copy:
        return ExitGateVerificationResponse(
            allow_exit=False,
            alarm_triggered=True,
            status="UNKNOWN_ITEM",
            message=f"UNKNOWN BARCODE: Tag '{clean_code}' is not registered in university library inventory. Security gate locked.",
            copy_code=clean_code,
            book_title=None,
            borrower_name=None,
            borrower_email=None,
            loan_id=None,
            due_date=None,
            timestamp=now_iso,
        )

    book = db.query(Book).filter(Book.id == copy.book_id).first()
    book_title = book.title if book else "Unknown Monograph"

    # Check for active loan
    active_loan = db.query(Loan).filter(
        Loan.copy_id == copy.id,
        Loan.returned_at.is_(None),
    ).order_by(Loan.id.desc()).first()

    if active_loan:
        borrower = db.query(User).filter(User.id == active_loan.student_id).first()
        borrower_name = borrower.full_name if borrower else f"Student #{active_loan.student_id}"
        borrower_email = borrower.email if borrower else None

        return ExitGateVerificationResponse(
            allow_exit=True,
            alarm_triggered=False,
            status="AUTHORIZED_CHECKOUT",
            message=f"AUTHORIZED DEPARTURE: Active checkout verified for {borrower_name}. Monograph '{book_title}' is permitted to exit.",
            copy_code=copy.copy_code,
            book_title=book_title,
            borrower_name=borrower_name,
            borrower_email=borrower_email,
            loan_id=active_loan.id,
            due_date=str(active_loan.due_date),
            timestamp=now_iso,
        )

    # Cross-check: Did an innocent student have an active hold on this copy where the checkout scan was missed?
    from app.models import BookHold
    active_hold = db.query(BookHold).filter(
        BookHold.copy_id == copy.id,
        BookHold.status.in_(["ready_for_pickup", "waiting"]),
    ).first()

    if active_hold:
        held_student = db.query(User).filter(User.id == active_hold.user_id).first()
        held_name = held_student.full_name if held_student else f"Student #{active_hold.user_id}"
        held_email = held_student.email if held_student else ""

        return ExitGateVerificationResponse(
            allow_exit=False,
            alarm_triggered=False,
            advisory_only=True,
            status="HOLD_CHECKOUT_INCOMPLETE",
            message=(
                f"🟡 CHECKOUT INCOMPLETE ADVISORY: '{book_title}' ({copy.copy_code}) was reserved by {held_name}, "
                f"but the desk or self-kiosk checkout scan was skipped! Please tap at the Express Kiosk to finalize."
            ),
            copy_code=copy.copy_code,
            book_title=book_title,
            borrower_name=None,
            borrower_email=None,
            held_by_name=held_name,
            loan_id=None,
            due_date=None,
            timestamp=now_iso,
        )
    else:
        with atomic_write(db):
            admin = db.query(User).first()
            if not admin:
                admin = User(
                    email="system_security@athenaeum.edu",
                    full_name="Security Sensor Daemon",
                    hashed_password="!",
                    role="librarian",
                    is_active=True,
                )
                db.add(admin)
                db.flush()

            event = InventoryEvent(
                copy_id=copy.id,
                auditor_id=admin.id,
                event_type="security_alarm",
                previous_status=copy.operational_status,
                new_status=copy.operational_status,
                notes="Unauthorized exit gate sensor trip: Book detected passing exit pedestal without active checkout loan.",
            )
            db.add(event)

        return ExitGateVerificationResponse(
            allow_exit=False,
            alarm_triggered=True,
            status="UNAUTHORIZED_ALARM",
            message=f"🚨 SECURITY ALARM TRIGGERED! Monograph '{book_title}' ({copy.copy_code}) was detected passing the exit sensor without an active loan! Gate locked.",
            copy_code=copy.copy_code,
            book_title=book_title,
            borrower_name=None,
            borrower_email=None,
            loan_id=None,
            due_date=None,
            timestamp=now_iso,
        )


def execute_self_checkout_service(
    db: Session,
    student_id_or_email: str,
    copy_code: str,
) -> SelfCheckoutResponse:
    """
    Automated self-service checkout with:
    1. Patron resolution (ID or email).
    2. Hold verification.
    3. Wrong title mismatch rejection with exact shelf slot guidance.
    4. Smart Copy Swapping: if patron grabbed another available copy of the same title,
       dynamically rebinds reservation to the copy in hand.
    5. Restricted copy protection: blocks taking another patron's reserved copy.
    6. Walk-in loan issuance if unreserved.
    """
    from datetime import datetime, timedelta
    from app.database import atomic_write
    from app.models import User, Book, BookCopy, BookHold, Loan, InventoryEvent

    clean_user = student_id_or_email.strip()
    clean_code = copy_code.strip()

    # 1. Resolve student
    student = None
    if clean_user.isdigit():
        student = db.query(User).filter(User.id == int(clean_user)).first()
    if not student:
        student = db.query(User).filter(User.email.ilike(clean_user)).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student account '{clean_user}' not found. Please verify your University ID or Email.",
        )

    # 2. Resolve scanned copy
    copy = db.query(BookCopy).filter(BookCopy.copy_code == clean_code).first()
    if not copy:
        clean_isbn = clean_code.replace("-", "").replace(" ", "")
        book_match = db.query(Book).filter(Book.isbn == clean_isbn).first()
        if book_match:
            copy = db.query(BookCopy).filter(
                BookCopy.book_id == book_match.id,
                BookCopy.operational_status == "available",
            ).first()

    if not copy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physical barcode '{clean_code}' was not found in library inventory.",
        )

    scanned_book = db.query(Book).filter(Book.id == copy.book_id).first()
    if not scanned_book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monograph metadata for this physical copy is missing.",
        )

    with atomic_write(db):
        # Check if this specific physical copy is already checked out by someone
        active_loan = db.query(Loan).filter(
            Loan.copy_id == copy.id,
            Loan.returned_at.is_(None),
        ).first()
        if active_loan:
            borrower = db.query(User).filter(User.id == active_loan.student_id).first()
            borrower_label = borrower.full_name if borrower else "another patron"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Physical copy '{copy.copy_code}' is currently on an active loan to {borrower_label}. It cannot be borrowed again until discharged.",
            )

        # Check if copy is in maintenance / lost
        if copy.operational_status not in ("available", "in_reshelving"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Physical copy '{copy.copy_code}' is marked under '{copy.operational_status}' and cannot be issued.",
            )

        # Check if the student has any active holds
        student_holds = db.query(BookHold).filter(
            BookHold.user_id == student.id,
            BookHold.status.in_(["ready_for_pickup", "waiting"]),
        ).all()

        matching_hold = next((h for h in student_holds if h.book_id == scanned_book.id), None)
        other_active_hold = next((h for h in student_holds if h.book_id != scanned_book.id), None)

        # Check if this copy is held by SOMEONE ELSE
        someone_elses_hold = db.query(BookHold).filter(
            BookHold.copy_id == copy.id,
            BookHold.user_id != student.id,
            BookHold.status.in_(["ready_for_pickup", "waiting"]),
        ).first()

        if someone_elses_hold:
            other_user = db.query(User).filter(User.id == someone_elses_hold.user_id).first()
            other_name = other_user.full_name if other_user else "another patron"
            loc = locate_book_on_shelf_service(db, scanned_book.id)
            return SelfCheckoutResponse(
                success=False,
                status="COPY_RESTRICTED",
                message=(
                    f"⚠️ COPY RESERVED FOR ANOTHER STUDENT: Physical copy '{copy.copy_code}' is currently allocated "
                    f"to a pending hold for {other_name}. You cannot borrow this specific copy."
                ),
                copy_code=copy.copy_code,
                book_title=scanned_book.title,
                student_name=student.full_name,
                guidance=f"Please return this copy to {loc.aisle}, {loc.bay}, {loc.shelf_tier_name}. Take your assigned copy.",
            )

        # Case 1: Student reserved a DIFFERENT book, but picked this book!
        if other_active_hold and not matching_hold:
            reserved_book = db.query(Book).filter(Book.id == other_active_hold.book_id).first()
            target_title = reserved_book.title if reserved_book else "your reserved monograph"
            loc = locate_book_on_shelf_service(db, other_active_hold.book_id)
            return SelfCheckoutResponse(
                success=False,
                status="WRONG_BOOK",
                message=(
                    f"❌ WRONG TITLE SCANNED: You scanned '{scanned_book.title}' ({copy.copy_code}), "
                    f"but your pending reservation is for '{target_title}'!"
                ),
                copy_code=copy.copy_code,
                book_title=scanned_book.title,
                student_name=student.full_name,
                guidance=(
                    f"Please put '{scanned_book.title}' back. Your reserved monograph '{target_title}' "
                    f"is located on {loc.aisle} ({loc.floor_name.split('—')[0].strip()}), {loc.bay}, {loc.shelf_tier_name}, Slot #{loc.slot_number}."
                ),
            )

        # Case 2: Smart Copy Swapping:
        # Student reserved this book, but was allocated copy X, while scanning copy Y!
        swap_applied = False
        original_code = None

        if matching_hold:
            if matching_hold.copy_id and matching_hold.copy_id != copy.id:
                old_copy = db.query(BookCopy).filter(BookCopy.id == matching_hold.copy_id).first()
                original_code = old_copy.copy_code if old_copy else f"Copy #{matching_hold.copy_id}"
                matching_hold.copy_id = copy.id
                swap_applied = True

            matching_hold.status = "fulfilled"
            matching_hold.fulfilled_at = datetime.utcnow()

        # Issue the loan
        due = datetime.utcnow().date() + timedelta(days=14)
        loan = Loan(
            student_id=student.id,
            copy_id=copy.id,
            issued_by_id=student.id,
            due_date=due,
        )
        db.add(loan)
        copy.operational_status = "available"
        copy.notes = f"Checked out via Self-Service Kiosk by {student.full_name} on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

        event = InventoryEvent(
            copy_id=copy.id,
            auditor_id=student.id,
            event_type="self_checkout",
            previous_status="available",
            new_status="available",
            notes=f"Self-service loan #{loan.id} issued. Smart swap: {swap_applied}.",
        )
        db.add(event)

    msg = (
        f"⚡ SMART COPY SWAP APPLIED: You picked Copy '{copy.copy_code}' instead of assigned '{original_code}'. "
        f"Since '{copy.copy_code}' was available, your reservation was dynamically rebound. Enjoy your reading!"
        if swap_applied
        else f"✓ CHECKOUT SUCCESSFUL: Monograph '{scanned_book.title}' ({copy.copy_code}) is now checked out to {student.full_name}. Due on {due}."
    )

    return SelfCheckoutResponse(
        success=True,
        status="SMART_SWAP_ISSUED" if swap_applied else "LOAN_ISSUED",
        message=msg,
        loan_id=loan.id,
        copy_code=copy.copy_code,
        book_title=scanned_book.title,
        student_name=student.full_name,
        due_date=str(due),
        swap_applied=swap_applied,
        original_copy_code=original_code,
    )
