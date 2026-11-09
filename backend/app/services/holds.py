"""
Book Waitlists & Holds Service Layer (CIRC-02).
Coordinates patron waitlist placement, FIFO queue management, copy allocation upon return,
pickup window expiration, hold fulfillment, and librarian queue oversight.
"""
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import atomic_write
from app.models import Book, BookCopy, BookHold, Loan, Notification, User
from app.schemas import BookHoldListResponse, BookHoldResponse
from app.services.email import email_service

logger = logging.getLogger("athenaeum.holds")

DEFAULT_PICKUP_WINDOW_DAYS = 7


def serialize_hold(hold: BookHold, queue_position: Optional[int] = None) -> BookHoldResponse:
    """Serializes a BookHold model into BookHoldResponse schema."""
    book_title = hold.book.title if hold.book else "Unknown Book"
    book_author = hold.book.author if hold.book else None
    book_isbn = hold.book.isbn if hold.book else None
    patron_name = hold.user.full_name if hold.user else None
    copy_code = hold.copy.copy_code if hold.copy else None

    return BookHoldResponse(
        id=hold.id,
        book_id=hold.book_id,
        book_title=book_title,
        book_author=book_author,
        book_isbn=book_isbn,
        user_id=hold.user_id,
        patron_name=patron_name,
        copy_id=hold.copy_id,
        copy_code=copy_code,
        status=hold.status,
        queue_position=queue_position,
        created_at=hold.created_at,
        allocated_at=hold.allocated_at,
        pickup_expires_at=hold.pickup_expires_at,
        fulfilled_at=hold.fulfilled_at,
        cancelled_at=hold.cancelled_at,
        cancellation_reason=hold.cancellation_reason,
    )


def compute_queue_position(db: Session, hold: BookHold) -> Optional[int]:
    """Computes dynamic 1-indexed FIFO queue position for waiting holds."""
    if hold.status != "waiting":
        return None

    count = db.execute(
        select(func.count(BookHold.id)).where(
            BookHold.book_id == hold.book_id,
            BookHold.status == "waiting",
            BookHold.created_at <= hold.created_at,
        )
    ).scalar() or 1
    return count


def place_hold_service(db: Session, user: User, book_id: int) -> BookHoldResponse:
    """
    Places an online loan booking or waitlist reservation for a monograph.
    Safeguards:
    - User must be active with student or teacher role.
    - Book exists and is not archived.
    - User cannot place duplicate active holds for the same book.
    - User cannot hold a book they currently have on loan.
    - If copies are available on the shelf, immediately reserves an available physical copy in 'ready_for_pickup' status.
    - If all copies are on loan or unavailable, places the patron in the FIFO waitlist queue ('waiting').
    """
    if user.role not in ("student", "teacher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student and teacher patrons can place book holds.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your patron account is currently inactive and cannot place holds.",
        )

    with atomic_write(db):
        book = db.execute(select(Book).where(Book.id == book_id)).scalar_one_or_none()
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book monograph not found.")

        if book.is_archived:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot place hold on an archived monograph.")

        # 1. Check if user already holds an active hold on this book
        existing_hold = db.execute(
            select(BookHold).where(
                BookHold.book_id == book_id,
                BookHold.user_id == user.id,
                BookHold.status.in_(["waiting", "ready_for_pickup"]),
            )
        ).scalar_one_or_none()

        if existing_hold:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active hold or reservation for this book.",
            )

        # 2. Check if user currently has an active loan for this book
        active_loan = db.execute(
            select(Loan)
            .join(BookCopy, Loan.copy_id == BookCopy.id)
            .where(
                Loan.student_id == user.id,
                Loan.returned_at.is_(None),
                BookCopy.book_id == book_id,
            )
        ).scalar_one_or_none()

        if active_loan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You currently have an active loan for a copy of this book.",
            )

        # 3. Check shelf availability: find first available unallocated copy
        loaned_copy_ids = select(Loan.copy_id).where(
            Loan.returned_at.is_(None)
        )
        allocated_copy_ids = select(BookHold.copy_id).where(
            BookHold.book_id == book_id,
            BookHold.status == "ready_for_pickup",
            BookHold.copy_id.isnot(None),
        )

        available_copy = db.execute(
            select(BookCopy).where(
                BookCopy.book_id == book_id,
                BookCopy.operational_status == "available",
                BookCopy.id.not_in(loaned_copy_ids),
                BookCopy.id.not_in(allocated_copy_ids),
            ).order_by(BookCopy.id.asc())
        ).scalars().first()

        now = datetime.utcnow()

        if available_copy:
            # Immediate online reservation for available physical copy
            deadline = now + timedelta(days=DEFAULT_PICKUP_WINDOW_DAYS)
            new_hold = BookHold(
                book_id=book_id,
                user_id=user.id,
                copy_id=available_copy.id,
                status="ready_for_pickup",
                allocated_at=now,
                pickup_expires_at=deadline,
                created_at=now,
            )
            db.add(new_hold)
            db.flush()
            db.refresh(new_hold)

            # Create in-app notification confirming reservation
            book_title = book.title if book else "Monograph"
            notification = Notification(
                user_id=user.id,
                notification_type="hold_ready",
                title="Online Loan Reservation Confirmed",
                message=(
                    f"Your online loan booking for '{book_title}' is confirmed! Copy {available_copy.copy_code} is reserved at the circulation desk. "
                    f"Please collect it before {deadline.strftime('%b %d, %Y')} using your Collection QR pass."
                ),
                created_at=now,
                dedup_key=f"online_reserve:{new_hold.id}:{int(now.timestamp())}",
            )
            db.add(notification)
            logger.info("Online loan reservation created: allocated copy %s to user %s (hold %s)", available_copy.id, user.id, new_hold.id)
            return serialize_hold(new_hold, queue_position=1)
        else:
            # 4. Monograph currently out of stock: queue patron into FIFO waitlist
            new_hold = BookHold(
                book_id=book_id,
                user_id=user.id,
                copy_id=None,
                status="waiting",
                created_at=now,
            )
            db.add(new_hold)
            db.flush()
            db.refresh(new_hold)

            queue_pos = compute_queue_position(db, new_hold)
            logger.info("Placed user %s on waitlist queue position %s for monograph %s", user.id, queue_pos, book_id)
            return serialize_hold(new_hold, queue_position=queue_pos)


def get_my_holds_service(db: Session, user_id: int) -> BookHoldListResponse:
    """Returns all holds belonging to the authenticated patron with queue positions."""
    holds = db.execute(
        select(BookHold)
        .where(BookHold.user_id == user_id)
        .order_by(BookHold.created_at.desc())
    ).scalars().all()

    items = [serialize_hold(h, queue_position=compute_queue_position(db, h)) for h in holds]
    return BookHoldListResponse(total=len(items), items=items)


def cancel_hold_service(
    db: Session,
    user: User,
    hold_id: int,
    reason: Optional[str] = None,
) -> BookHoldResponse:
    """
    Cancels a hold. If the hold had an allocated copy in 'ready_for_pickup',
    automatically reallocates the released copy to the next waiting patron.
    """
    with atomic_write(db):
        hold = db.execute(select(BookHold).where(BookHold.id == hold_id)).scalar_one_or_none()
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book hold record not found.")

        # Patrons can only cancel their own holds; librarians can cancel any hold
        if user.role != "librarian" and hold.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to cancel this hold.")

        if hold.status not in ("waiting", "ready_for_pickup"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel a hold in '{hold.status}' status.",
            )

        released_copy_id = hold.copy_id if hold.status == "ready_for_pickup" else None

        hold.status = "cancelled"
        hold.cancelled_at = datetime.utcnow()
        hold.cancellation_reason = reason or ("Cancelled by patron" if user.id == hold.user_id else "Cancelled by librarian")
        db.add(hold)

        # If a copy was released, advance queue to the next waiting patron
        if released_copy_id:
            advance_queue_for_copy(db, hold.book_id, released_copy_id)

        return serialize_hold(hold)


def advance_queue_for_copy(db: Session, book_id: int, copy_id: int) -> Optional[BookHold]:
    """
    Allocates an available copy to the oldest eligible 'waiting' hold for the book.
    Updates hold status to 'ready_for_pickup', sets pickup deadline, and issues alert.
    """
    next_hold = db.execute(
        select(BookHold)
        .where(BookHold.book_id == book_id, BookHold.status == "waiting")
        .order_by(BookHold.created_at.asc())
    ).scalars().first()

    if not next_hold:
        return None

    now = datetime.utcnow()
    deadline = now + timedelta(days=DEFAULT_PICKUP_WINDOW_DAYS)

    next_hold.copy_id = copy_id
    next_hold.status = "ready_for_pickup"
    next_hold.allocated_at = now
    next_hold.pickup_expires_at = deadline
    db.add(next_hold)

    # In-app notification
    book_title = next_hold.book.title if next_hold.book else "Monograph"
    notification = Notification(
        user_id=next_hold.user_id,
        notification_type="hold_ready",
        title="Your Book Hold is Ready for Pickup",
        message=(
            f"A copy of '{book_title}' is ready for collection at the circulation desk. "
            f"Please collect it before {deadline.strftime('%b %d, %Y')}."
        ),
        created_at=now,
        dedup_key=f"hold_ready:{next_hold.id}:{int(now.timestamp())}",
    )
    db.add(notification)

    logger.info("Allocated copy %s to hold %s (user %s)", copy_id, next_hold.id, next_hold.user_id)
    return next_hold


def fulfill_hold_on_loan_issue(
    db: Session,
    student_id: int,
    copy: BookCopy,
) -> Optional[BookHold]:
    """
    Integrates hold fulfillment into loan issuance:
    1. If copy is reserved for another patron, rejects the issuance.
    2. If copy is reserved for THIS student, fulfills the hold.
    """
    active_hold_for_copy = db.execute(
        select(BookHold).where(
            BookHold.copy_id == copy.id,
            BookHold.status == "ready_for_pickup",
        )
    ).scalar_one_or_none()

    if active_hold_for_copy:
        if active_hold_for_copy.user_id != student_id:
            patron_info = active_hold_for_copy.user.full_name if active_hold_for_copy.user else f"Patron #{active_hold_for_copy.user_id}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This copy ({copy.copy_code}) is reserved on hold for {patron_info} awaiting pickup.",
            )

        # Fulfill hold
        active_hold_for_copy.status = "fulfilled"
        active_hold_for_copy.fulfilled_at = datetime.utcnow()
        db.add(active_hold_for_copy)
        logger.info("Fulfilled hold %s for student %s on copy %s", active_hold_for_copy.id, student_id, copy.id)
        return active_hold_for_copy

    return None


def get_librarian_holds_service(
    db: Session,
    status_filter: Optional[str] = None,
    book_id: Optional[int] = None,
) -> BookHoldListResponse:
    """Allows librarians to view and manage all holds across the library system."""
    query = select(BookHold).order_by(BookHold.created_at.desc())
    if status_filter:
        query = query.where(BookHold.status == status_filter)
    if book_id:
        query = query.where(BookHold.book_id == book_id)

    holds = db.execute(query).scalars().all()
    items = [serialize_hold(h, queue_position=compute_queue_position(db, h)) for h in holds]
    return BookHoldListResponse(total=len(items), items=items)


def sweep_expired_holds_service(db: Session) -> int:
    """
    Finds ready_for_pickup holds whose pickup deadline has elapsed.
    Marks them expired and advances the queue to the next waiting patron.
    """
    now = datetime.utcnow()
    with atomic_write(db):
        expired_holds = db.execute(
            select(BookHold).where(
                BookHold.status == "ready_for_pickup",
                BookHold.pickup_expires_at < now,
            )
        ).scalars().all()

        count = len(expired_holds)
        for hold in expired_holds:
            released_copy_id = hold.copy_id
            hold.status = "expired"
            db.add(hold)

            if released_copy_id:
                advance_queue_for_copy(db, hold.book_id, released_copy_id)

        return count
