"""
Catalogue and physical inventory service layer.
Coordinates business logic, authorization rules, transaction boundaries, and data-integrity protections.
"""
import math
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud import catalogue as crud
from app.database import atomic_write
from app.models import BookCopy, Loan
from app.schemas import (
    BookCreate,
    BookDetailResponse,
    BookPaginationResponse,
    BookResponse,
    BookUpdate,
    BookCopyCreate,
    BookCopyResponse,
    BookCopyUpdate,
)


def _get_single_book_counts(db: Session, book_id: int) -> Tuple[int, int]:
    """Computes total_copies and available_copies for a single book."""
    active_loans_subq = (
        select(Loan.copy_id)
        .where(Loan.returned_at.is_(None))
        .scalar_subquery()
    )
    avail_count = db.execute(
        select(func.count(BookCopy.id)).where(
            BookCopy.book_id == book_id,
            BookCopy.operational_status == "available",
            BookCopy.id.not_in(active_loans_subq),
        )
    ).scalar() or 0

    total_count = db.execute(
        select(func.count(BookCopy.id)).where(BookCopy.book_id == book_id)
    ).scalar() or 0

    return total_count, avail_count


def list_books_service(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    category: Optional[str] = None,
    include_archived: bool = False,
    is_librarian: bool = False,
) -> BookPaginationResponse:
    """
    Retrieves paginated catalogue books with total and available copy counts.
    Enforces that non-librarians cannot view archived books.
    """
    effective_include_archived = include_archived if is_librarian else False

    books, total_count, total_map, avail_map = crud.get_books(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        include_archived=effective_include_archived,
    )

    items: List[BookResponse] = []
    for b in books:
        items.append(
            BookResponse(
                id=b.id,
                title=b.title,
                author=b.author,
                isbn=b.isbn,
                category=b.category,
                description=b.description,
                is_archived=b.is_archived,
                total_copies=total_map.get(b.id, 0),
                available_copies=avail_map.get(b.id, 0),
                created_at=b.created_at,
                updated_at=b.updated_at,
            )
        )

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

    return BookPaginationResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_book_detail_service(
    db: Session,
    book_id: int,
    is_librarian: bool = False,
) -> BookDetailResponse:
    """
    Retrieves detailed metadata and copy inventory for a specific book.
    Returns 404 if the book is missing or if archived and requested by a non-librarian.
    """
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )

    if book.is_archived and not is_librarian:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )

    copies = crud.get_copies_for_book(db, book_id)
    copy_ids = [c.id for c in copies]
    active_loan_ids = crud.get_active_loans_for_copies(db, copy_ids)

    copy_responses: List[BookCopyResponse] = []
    avail_count = 0
    for c in copies:
        is_borrowed = c.id in active_loan_ids
        effective_status = "borrowed" if is_borrowed else c.operational_status
        if c.operational_status == "available" and not is_borrowed:
            avail_count += 1

        copy_responses.append(
            BookCopyResponse(
                id=c.id,
                book_id=c.book_id,
                copy_code=c.copy_code,
                operational_status=c.operational_status,
                is_borrowed=is_borrowed,
                effective_status=effective_status,
                notes=c.notes,
                added_at=c.added_at,
            )
        )

    return BookDetailResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        isbn=book.isbn,
        category=book.category,
        description=book.description,
        is_archived=book.is_archived,
        total_copies=len(copies),
        available_copies=avail_count,
        created_at=book.created_at,
        updated_at=book.updated_at,
        copies=copy_responses,
    )


def create_book_service(db: Session, book_in: BookCreate) -> BookResponse:
    """Creates a new book title in an atomic transaction."""
    with atomic_write(db):
        if book_in.isbn:
            existing = crud.get_book_by_isbn(db, book_in.isbn)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A book with ISBN '{book_in.isbn}' already exists.",
                )
        book = crud.create_book(db, book_in)
        return BookResponse(
            id=book.id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            category=book.category,
            description=book.description,
            is_archived=book.is_archived,
            total_copies=0,
            available_copies=0,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )


def update_book_service(
    db: Session,
    book_id: int,
    book_in: BookUpdate,
) -> BookResponse:
    """Updates book metadata atomically, verifying ISBN uniqueness."""
    with atomic_write(db):
        book = crud.get_book(db, book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )

        if book_in.isbn and book_in.isbn != book.isbn:
            existing = crud.get_book_by_isbn(db, book_in.isbn)
            if existing and existing.id != book.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A book with ISBN '{book_in.isbn}' already exists.",
                )

        book = crud.update_book(db, book, book_in)
        total_copies, avail_copies = _get_single_book_counts(db, book.id)

        return BookResponse(
            id=book.id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            category=book.category,
            description=book.description,
            is_archived=book.is_archived,
            total_copies=total_copies,
            available_copies=avail_copies,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )


def archive_book_service(db: Session, book_id: int) -> BookResponse:
    """
    Soft-archives a book record, preserving copies and historical loan relationships.
    """
    with atomic_write(db):
        book = crud.get_book(db, book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )

        book = crud.archive_book(db, book)
        total_copies, avail_copies = _get_single_book_counts(db, book.id)

        return BookResponse(
            id=book.id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            category=book.category,
            description=book.description,
            is_archived=book.is_archived,
            total_copies=total_copies,
            available_copies=avail_copies,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )


def list_copies_for_book_service(
    db: Session,
    book_id: int,
    is_librarian: bool = False,
) -> List[BookCopyResponse]:
    """Lists physical copies associated with a book title."""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )
    if book.is_archived and not is_librarian:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )

    copies = crud.get_copies_for_book(db, book_id)
    copy_ids = [c.id for c in copies]
    active_loan_ids = crud.get_active_loans_for_copies(db, copy_ids)

    results: List[BookCopyResponse] = []
    for c in copies:
        is_borrowed = c.id in active_loan_ids
        effective_status = "borrowed" if is_borrowed else c.operational_status
        results.append(
            BookCopyResponse(
                id=c.id,
                book_id=c.book_id,
                copy_code=c.copy_code,
                operational_status=c.operational_status,
                is_borrowed=is_borrowed,
                effective_status=effective_status,
                notes=c.notes,
                added_at=c.added_at,
            )
        )
    return results


def get_copy_service(
    db: Session,
    copy_id: int,
    is_librarian: bool = False,
) -> BookCopyResponse:
    """Retrieves a single copy by ID with its dynamic borrowing status."""
    copy = crud.get_copy(db, copy_id)
    if not copy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book copy not found.",
        )

    if copy.book.is_archived and not is_librarian:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book copy not found.",
        )

    is_borrowed = crud.has_active_loan(db, copy.id)
    effective_status = "borrowed" if is_borrowed else copy.operational_status

    return BookCopyResponse(
        id=copy.id,
        book_id=copy.book_id,
        copy_code=copy.copy_code,
        operational_status=copy.operational_status,
        is_borrowed=is_borrowed,
        effective_status=effective_status,
        notes=copy.notes,
        added_at=copy.added_at,
    )


def add_copy_service(
    db: Session,
    book_id: int,
    copy_in: BookCopyCreate,
) -> BookCopyResponse:
    """Adds a physical copy to an active book title in an atomic transaction."""
    with atomic_write(db):
        book = crud.get_book(db, book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )
        if book.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add physical copies to an archived book.",
            )

        existing = crud.get_copy_by_code(db, copy_in.copy_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A physical copy with barcode/code '{copy_in.copy_code}' already exists.",
            )

        copy = crud.create_copy(db, book_id, copy_in)
        return BookCopyResponse(
            id=copy.id,
            book_id=copy.book_id,
            copy_code=copy.copy_code,
            operational_status=copy.operational_status,
            is_borrowed=False,
            effective_status=copy.operational_status,
            notes=copy.notes,
            added_at=copy.added_at,
        )


def update_copy_service(
    db: Session,
    copy_id: int,
    copy_in: BookCopyUpdate,
) -> BookCopyResponse:
    """Updates permitted copy metadata and operational status safely."""
    with atomic_write(db):
        copy = crud.get_copy(db, copy_id)
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book copy not found.",
            )

        has_active = crud.has_active_loan(db, copy.id)
        if has_active:
            if copy_in.operational_status == "available":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set copy status to 'available' while it has an active loan.",
                )
            if copy_in.operational_status == "retired":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot retire a copy that currently has an active loan.",
                )

        copy = crud.update_copy(db, copy, copy_in)
        effective = "borrowed" if has_active else copy.operational_status

        return BookCopyResponse(
            id=copy.id,
            book_id=copy.book_id,
            copy_code=copy.copy_code,
            operational_status=copy.operational_status,
            is_borrowed=has_active,
            effective_status=effective,
            notes=copy.notes,
            added_at=copy.added_at,
        )


def retire_copy_service(db: Session, copy_id: int) -> BookCopyResponse:
    """Retires a physical copy safely, preventing retirement if currently loaned."""
    with atomic_write(db):
        copy = crud.get_copy(db, copy_id)
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book copy not found.",
            )

        if crud.has_active_loan(db, copy.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot retire a copy that currently has an active loan.",
            )

        copy = crud.retire_copy(db, copy)
        return BookCopyResponse(
            id=copy.id,
            book_id=copy.book_id,
            copy_code=copy.copy_code,
            operational_status=copy.operational_status,
            is_borrowed=False,
            effective_status=copy.operational_status,
            notes=copy.notes,
            added_at=copy.added_at,
        )


def delete_copy_service(db: Session, copy_id: int) -> dict:
    """
    Safely handles physical copy deletion.
    If historical loans exist, rejects hard deletion to preserve historical records,
    instructing the caller to retire the copy instead.
    If unreferenced, removes the copy record.
    """
    with atomic_write(db):
        copy = crud.get_copy(db, copy_id)
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book copy not found.",
            )

        if crud.has_active_loan(db, copy.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete a copy that currently has an active loan.",
            )

        if crud.has_historical_loans(db, copy.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot physically delete copy with historical loan records; retire the copy instead.",
            )

        crud.delete_copy(db, copy)
        return {"detail": "Book copy deleted successfully."}
