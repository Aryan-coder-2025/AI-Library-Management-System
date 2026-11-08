from app.utils.date import get_utc_today
"""
Notifications service for patron alerts (CIRC-04).
Handles in-app notification creation, retrieval, status updates, and
idempotent sweep generation for overdue loans.
"""
import math
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.database import atomic_write
from app.models import Notification, Loan, BookCopy, User
from app.schemas import (
    NotificationResponse,
    NotificationPaginationResponse,
    NotificationUnreadCountResponse,
    SweepNotificationResponse,
)


def serialize_notification(notification: Notification) -> NotificationResponse:
    book_id = None
    book_title = None

    # 1. Check dedup_key for course_reading_list
    if notification.dedup_key:
        if notification.dedup_key.startswith("reading_list:"):
            parts = notification.dedup_key.split(":")
            if len(parts) >= 3 and parts[2].isdigit():
                book_id = int(parts[2])

    # 2. Check loan relationship if available
    if not book_id and getattr(notification, "loan", None):
        loan = notification.loan
        if getattr(loan, "copy", None):
            book_id = loan.copy.book_id
            if getattr(loan.copy, "book", None):
                book_title = loan.copy.book.title

    # 3. Extract quoted title from message if book_title not yet found
    if not book_title and notification.message:
        import re
        match = re.search(r"'([^']+)'", notification.message)
        if match:
            book_title = match.group(1)

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        loan_id=notification.loan_id,
        book_id=book_id,
        book_title=book_title,
        notification_type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        target_due_date=notification.target_due_date,
        is_read=notification.is_read,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


def list_user_notifications_service(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
) -> NotificationPaginationResponse:
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    unread_count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    ) or 0

    offset = (page - 1) * page_size
    stmt = query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(offset).limit(page_size)
    notifications = db.execute(stmt).scalars().all()

    items = [serialize_notification(n) for n in notifications]
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return NotificationPaginationResponse(
        items=items,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_unread_count_service(db: Session, user_id: int) -> NotificationUnreadCountResponse:
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    ) or 0
    return NotificationUnreadCountResponse(unread_count=count)


def mark_notification_read_service(
    db: Session,
    notification_id: int,
    current_user: User,
) -> NotificationResponse:
    with atomic_write(db):
        notification = db.get(Notification, notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )
        if notification.user_id != current_user.id and current_user.role != "librarian":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot modify notifications belonging to another user.",
            )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            db.add(notification)
            db.flush()
            db.refresh(notification)

        return serialize_notification(notification)


def mark_all_notifications_read_service(
    db: Session,
    user_id: int,
) -> Dict[str, Any]:
    with atomic_write(db):
        now = datetime.now(timezone.utc)
        stmt = (
            Notification.__table__.update()
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=now)
        )
        result = db.execute(stmt)
        return {"updated_count": result.rowcount}


def sweep_and_generate_overdue_notifications(
    db: Session,
    as_of_date: Optional[date] = None,
) -> SweepNotificationResponse:
    """
    Scans all active loans whose due date is past `as_of_date` (defaults to today).
    Creates an overdue notification for each overdue loan if one has not already been created
    for that specific loan and due date combination (idempotent deduplication via dedup_key).
    """
    if as_of_date is None:
        as_of_date = get_utc_today()

    with atomic_write(db):
        stmt = (
            select(Loan)
            .options(
                joinedload(Loan.copy).joinedload(BookCopy.book),
                joinedload(Loan.student),
            )
            .where(
                Loan.returned_at.is_(None),
                Loan.due_date < as_of_date,
            )
        )
        overdue_loans = db.execute(stmt).scalars().all()

        created_count = 0
        for loan in overdue_loans:
            dedup_key = f"overdue:{loan.id}:{loan.due_date.isoformat()}"

            existing = db.execute(
                select(Notification.id).where(Notification.dedup_key == dedup_key)
            ).first()

            if existing:
                continue

            book_title = (
                loan.copy.book.title
                if loan.copy and loan.copy.book
                else "your borrowed book"
            )
            days_overdue = (as_of_date - loan.due_date).days

            notification = Notification(
                user_id=loan.student_id,
                loan_id=loan.id,
                notification_type="overdue",
                title=f"Overdue Notice: {book_title[:60]}",
                message=(
                    f"Your loan for '{book_title}' is {days_overdue} day(s) overdue "
                    f"(due date was {loan.due_date.isoformat()}). Please return the book to "
                    f"the library circulation desk promptly to maintain good account standing."
                ),
                target_due_date=loan.due_date,
                is_read=False,
                dedup_key=dedup_key,
                created_at=datetime.now(timezone.utc),
            )
            try:
                db.add(notification)
                db.flush()
                created_count += 1
            except IntegrityError:
                # Concurrent runner inserted dedup_key
                db.rollback()
                continue

        return SweepNotificationResponse(new_notifications=created_count)
