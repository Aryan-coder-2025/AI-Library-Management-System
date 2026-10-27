"""
Catalogue and inventory CRUD operations.
Handles database queries and persistence for books, physical copies, and inventory queries.
"""
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Book, BookCopy, Loan
from app.schemas import BookCreate, BookUpdate, BookCopyCreate, BookCopyUpdate


def get_book(db: Session, book_id: int) -> Optional[Book]:
    """Retrieves a single book by ID."""
    return db.execute(select(Book).where(Book.id == book_id)).scalar_one_or_none()


def get_book_by_isbn(db: Session, isbn: str) -> Optional[Book]:
    """Retrieves a single book by its ISBN."""
    return db.execute(select(Book).where(Book.isbn == isbn)).scalar_one_or_none()


def get_books(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    category: Optional[str] = None,
    include_archived: bool = False,
) -> Tuple[List[Book], int, Dict[int, int], Dict[int, int]]:
    """
    Returns a paginated list of books, total match count, and copy counts.
    Avoids N+1 queries by aggregating copy and availability counts in two grouped queries.
    """
    query = select(Book)

    if not include_archived:
        query = query.where(Book.is_archived.is_(False))

    if category:
        query = query.where(Book.category.ilike(category.strip()))

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Book.title.ilike(term),
                Book.author.ilike(term),
                Book.isbn.ilike(term),
            )
        )

    # Total matching records count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.execute(count_query).scalar() or 0

    # Paginated books
    offset = (page - 1) * page_size
    books = db.execute(
        query.order_by(Book.id.asc()).offset(offset).limit(page_size)
    ).scalars().all()

    if not books:
        return [], total_count, {}, {}

    book_ids = [book.id for book in books]

    # Total copies count per book
    total_copies_stmt = (
        select(BookCopy.book_id, func.count(BookCopy.id).label("total_count"))
        .where(BookCopy.book_id.in_(book_ids))
        .group_by(BookCopy.book_id)
    )
    total_copies_map: Dict[int, int] = dict(db.execute(total_copies_stmt).all())

    # Active loans subquery
    active_loans_subq = (
        select(Loan.copy_id)
        .where(Loan.returned_at.is_(None))
        .scalar_subquery()
    )

    # Available copies count per book: operational_status == 'available' and no active unreturned loan
    avail_copies_stmt = (
        select(BookCopy.book_id, func.count(BookCopy.id).label("avail_count"))
        .where(
            BookCopy.book_id.in_(book_ids),
            BookCopy.operational_status == "available",
            BookCopy.id.not_in(active_loans_subq),
        )
        .group_by(BookCopy.book_id)
    )
    avail_copies_map: Dict[int, int] = dict(db.execute(avail_copies_stmt).all())

    return books, total_count, total_copies_map, avail_copies_map


def create_book(db: Session, book_in: BookCreate) -> Book:
    """Creates and persists a new book."""
    book = Book(
        title=book_in.title,
        author=book_in.author,
        isbn=book_in.isbn,
        category=book_in.category,
        description=book_in.description,
        is_archived=False,
    )
    db.add(book)
    db.flush()
    db.refresh(book)
    return book


def update_book(db: Session, book: Book, book_in: BookUpdate) -> Book:
    """Updates specified fields on an existing book record."""
    update_data = book_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(book, field, value)
    book.updated_at = datetime.utcnow()
    db.add(book)
    db.flush()
    db.refresh(book)
    return book


def archive_book(db: Session, book: Book) -> Book:
    """Soft-archives a book record, preserving copies and historical relationships."""
    book.is_archived = True
    book.updated_at = datetime.utcnow()
    db.add(book)
    db.flush()
    db.refresh(book)
    return book


def get_copy(db: Session, copy_id: int) -> Optional[BookCopy]:
    """Retrieves a single copy by ID."""
    return db.execute(select(BookCopy).where(BookCopy.id == copy_id)).scalar_one_or_none()


def get_copy_by_code(db: Session, copy_code: str) -> Optional[BookCopy]:
    """Retrieves a single copy by its unique copy code."""
    return db.execute(select(BookCopy).where(BookCopy.copy_code == copy_code)).scalar_one_or_none()


def get_copies_for_book(db: Session, book_id: int) -> List[BookCopy]:
    """Retrieves all copies associated with a book, ordered by ID."""
    stmt = (
        select(BookCopy)
        .where(BookCopy.book_id == book_id)
        .order_by(BookCopy.id.asc())
    )
    return db.execute(stmt).scalars().all()


def get_active_loans_for_copies(db: Session, copy_ids: List[int]) -> Set[int]:
    """Returns a set of copy IDs that have an active (unreturned) loan."""
    if not copy_ids:
        return set()
    stmt = (
        select(Loan.copy_id)
        .where(Loan.copy_id.in_(copy_ids), Loan.returned_at.is_(None))
    )
    return set(db.execute(stmt).scalars().all())


def has_active_loan(db: Session, copy_id: int) -> bool:
    """Checks whether the specified copy currently has an active unreturned loan."""
    stmt = (
        select(func.count(Loan.id))
        .where(Loan.copy_id == copy_id, Loan.returned_at.is_(None))
    )
    count = db.execute(stmt).scalar() or 0
    return count > 0


def has_historical_loans(db: Session, copy_id: int) -> bool:
    """Checks whether the specified copy has any associated loan records (active or returned)."""
    stmt = (
        select(func.count(Loan.id))
        .where(Loan.copy_id == copy_id)
    )
    count = db.execute(stmt).scalar() or 0
    return count > 0


def create_copy(db: Session, book_id: int, copy_in: BookCopyCreate) -> BookCopy:
    """Creates and persists a new physical copy."""
    copy = BookCopy(
        book_id=book_id,
        copy_code=copy_in.copy_code,
        operational_status=copy_in.operational_status,
        notes=copy_in.notes,
    )
    db.add(copy)
    db.flush()
    db.refresh(copy)
    return copy


def update_copy(db: Session, copy: BookCopy, copy_in: BookCopyUpdate) -> BookCopy:
    """Updates permitted metadata and operational status of a physical copy."""
    update_data = copy_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(copy, field, value)
    db.add(copy)
    db.flush()
    db.refresh(copy)
    return copy


def retire_copy(db: Session, copy: BookCopy) -> BookCopy:
    """Sets a copy's operational status to retired."""
    copy.operational_status = "retired"
    db.add(copy)
    db.flush()
    db.refresh(copy)
    return copy


def delete_copy(db: Session, copy: BookCopy) -> None:
    """Physically deletes a copy record."""
    db.delete(copy)
    db.flush()
