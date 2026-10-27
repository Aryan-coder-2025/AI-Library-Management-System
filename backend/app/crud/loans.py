"""
Loan circulation CRUD operations.
Handles database queries and persistence for book loans and circulation tracking.
"""
from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import BookCopy, Loan, User


def get_loan(db: Session, loan_id: int) -> Optional[Loan]:
    """Retrieves a single loan record by ID with relations eagerly loaded."""
    stmt = (
        select(Loan)
        .options(
            joinedload(Loan.student),
            joinedload(Loan.copy).joinedload(BookCopy.book),
            joinedload(Loan.issued_by),
        )
        .where(Loan.id == loan_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieves a user by ID."""
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def get_copy_by_id(db: Session, copy_id: int) -> Optional[BookCopy]:
    """Retrieves a physical copy by ID with its parent book eagerly loaded."""
    stmt = (
        select(BookCopy)
        .options(joinedload(BookCopy.book))
        .where(BookCopy.id == copy_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def has_active_loan_for_copy(db: Session, copy_id: int) -> bool:
    """Checks whether the specified physical copy currently has an active unreturned loan."""
    stmt = (
        select(func.count(Loan.id))
        .where(Loan.copy_id == copy_id, Loan.returned_at.is_(None))
    )
    count = db.execute(stmt).scalar() or 0
    return count > 0


def get_student_active_loan_count(db: Session, student_id: int) -> int:
    """Returns the count of active (unreturned) loans for a specific student."""
    stmt = (
        select(func.count(Loan.id))
        .where(Loan.student_id == student_id, Loan.returned_at.is_(None))
    )
    return db.execute(stmt).scalar() or 0


def student_has_overdue_loans(db: Session, student_id: int, as_of_date: date) -> bool:
    """Checks whether a student has any active loan whose due date is prior to as_of_date."""
    stmt = (
        select(func.count(Loan.id))
        .where(
            Loan.student_id == student_id,
            Loan.returned_at.is_(None),
            Loan.due_date < as_of_date,
        )
    )
    count = db.execute(stmt).scalar() or 0
    return count > 0


def create_loan(
    db: Session,
    student_id: int,
    copy_id: int,
    issued_by_id: int,
    issued_at: datetime,
    due_date: date,
) -> Loan:
    """Creates and persists a new loan record."""
    loan = Loan(
        student_id=student_id,
        copy_id=copy_id,
        issued_by_id=issued_by_id,
        issued_at=issued_at,
        due_date=due_date,
        returned_at=None,
    )
    db.add(loan)
    db.flush()
    # Eagerly load relationships so they are available after creation
    return get_loan(db, loan.id) or loan


def return_loan(db: Session, loan: Loan, returned_at: datetime) -> Loan:
    """Sets the returned_at timestamp on an active loan."""
    loan.returned_at = returned_at
    db.add(loan)
    db.flush()
    db.refresh(loan)
    return loan


def get_loans(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    student_id: Optional[int] = None,
    copy_id: Optional[int] = None,
    book_id: Optional[int] = None,
    status: Optional[str] = None,
    as_of_date: Optional[date] = None,
) -> Tuple[List[Loan], int]:
    """
    Returns a paginated list of loans with eagerly loaded relations and total count.
    Supports filtering by student_id, copy_id, book_id, and status ('active', 'returned', 'overdue').
    """
    today = as_of_date or date.today()
    query = (
        select(Loan)
        .options(
            joinedload(Loan.student),
            joinedload(Loan.copy).joinedload(BookCopy.book),
            joinedload(Loan.issued_by),
        )
    )

    if student_id is not None:
        query = query.where(Loan.student_id == student_id)

    if copy_id is not None:
        query = query.where(Loan.copy_id == copy_id)

    if book_id is not None:
        query = query.join(Loan.copy).where(BookCopy.book_id == book_id)

    if status:
        normalized_status = status.strip().lower()
        if normalized_status == "active":
            query = query.where(Loan.returned_at.is_(None), Loan.due_date >= today)
        elif normalized_status == "returned":
            query = query.where(Loan.returned_at.is_not(None))
        elif normalized_status == "overdue":
            query = query.where(Loan.returned_at.is_(None), Loan.due_date < today)

    # Count total matching loans
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.execute(count_query).scalar() or 0

    # Paginated results ordered newest first
    offset = (page - 1) * page_size
    loans = db.execute(
        query.order_by(Loan.issued_at.desc(), Loan.id.desc())
        .offset(offset)
        .limit(page_size)
    ).scalars().all()

    return loans, total_count
