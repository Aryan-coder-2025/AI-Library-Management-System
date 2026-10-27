"""
Catalogue and physical inventory API router.
Provides endpoints for books and physical copy management.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user, require_librarian
from app.models import User
from app.schemas import (
    BookCreate,
    BookDetailResponse,
    BookPaginationResponse,
    BookResponse,
    BookUpdate,
    BookCopyCreate,
    BookCopyResponse,
    BookCopyUpdate,
    MessageResponse,
)
from app.services import catalogue as catalogue_service

router = APIRouter(tags=["catalogue"])


# ── Books Endpoints ───────────────────────────────────────────────────────────

@router.get(
    "/api/books",
    response_model=BookPaginationResponse,
    summary="List books with pagination, search, and category filtering",
)
def list_books(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by title, author, or ISBN"),
    category: Optional[str] = Query(None, description="Filter by category"),
    include_archived: bool = Query(False, description="Include archived books (librarian only)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns a paginated list of catalogue books.
    Available to students and librarians. Students only see active (non-archived) books.
    """
    is_librarian = current_user.role == "librarian"
    return catalogue_service.list_books_service(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        include_archived=include_archived,
        is_librarian=is_librarian,
    )


@router.post(
    "/api/books",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new catalogue book record (librarian only)",
)
def create_book(
    book_in: BookCreate,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Creates a new book title in the catalogue. Librarian only."""
    return catalogue_service.create_book_service(db=db, book_in=book_in)


@router.get(
    "/api/books/{book_id}",
    response_model=BookDetailResponse,
    summary="Retrieve detailed book metadata and physical copies",
)
def get_book_detail(
    book_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full details for a book, including its physical copies and availability.
    Available to students and librarians.
    """
    is_librarian = current_user.role == "librarian"
    return catalogue_service.get_book_detail_service(
        db=db,
        book_id=book_id,
        is_librarian=is_librarian,
    )


@router.patch(
    "/api/books/{book_id}",
    response_model=BookResponse,
    summary="Update catalogue book metadata (librarian only)",
)
def update_book(
    book_id: int,
    book_in: BookUpdate,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Updates book metadata. Librarian only."""
    return catalogue_service.update_book_service(
        db=db,
        book_id=book_id,
        book_in=book_in,
    )


@router.post(
    "/api/books/{book_id}/archive",
    response_model=BookResponse,
    summary="Archive a book record (librarian only)",
)
def archive_book(
    book_id: int,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Soft-archives a book record, preserving copies and historical loan relationships.
    Librarian only.
    """
    return catalogue_service.archive_book_service(db=db, book_id=book_id)


@router.delete(
    "/api/books/{book_id}",
    response_model=BookResponse,
    summary="Soft-delete/archive a book record (librarian only)",
)
def delete_book(
    book_id: int,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Soft-deletes (archives) a book record to preserve data integrity and loan history.
    Librarian only.
    """
    return catalogue_service.archive_book_service(db=db, book_id=book_id)


# ── Physical Copies Endpoints ─────────────────────────────────────────────────

@router.get(
    "/api/books/{book_id}/copies",
    response_model=List[BookCopyResponse],
    summary="List physical copies belonging to a book",
)
def list_copies_for_book(
    book_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Lists physical copies belonging to a book with derived borrowing status.
    Available to students and librarians.
    """
    is_librarian = current_user.role == "librarian"
    return catalogue_service.list_copies_for_book_service(
        db=db,
        book_id=book_id,
        is_librarian=is_librarian,
    )


@router.post(
    "/api/books/{book_id}/copies",
    response_model=BookCopyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a physical copy to a book (librarian only)",
)
def add_copy(
    book_id: int,
    copy_in: BookCopyCreate,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Adds a physical copy with a unique barcode/code. Librarian only."""
    return catalogue_service.add_copy_service(
        db=db,
        book_id=book_id,
        copy_in=copy_in,
    )


@router.get(
    "/api/copies/{copy_id}",
    response_model=BookCopyResponse,
    summary="Retrieve an individual copy by ID",
)
def get_copy(
    copy_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieves an individual physical copy. Available to students and librarians."""
    is_librarian = current_user.role == "librarian"
    return catalogue_service.get_copy_service(
        db=db,
        copy_id=copy_id,
        is_librarian=is_librarian,
    )


@router.patch(
    "/api/copies/{copy_id}",
    response_model=BookCopyResponse,
    summary="Update physical copy metadata and operational status (librarian only)",
)
def update_copy(
    copy_id: int,
    copy_in: BookCopyUpdate,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Updates operational status ('available', 'maintenance', 'lost', 'retired') and notes.
    Prevents setting active loans to 'available' or 'retired'. Librarian only.
    """
    return catalogue_service.update_copy_service(
        db=db,
        copy_id=copy_id,
        copy_in=copy_in,
    )


@router.post(
    "/api/copies/{copy_id}/retire",
    response_model=BookCopyResponse,
    summary="Retire a physical copy safely (librarian only)",
)
def retire_copy(
    copy_id: int,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Retires a physical copy from active circulation while preserving historical loans.
    Librarian only.
    """
    return catalogue_service.retire_copy_service(db=db, copy_id=copy_id)


@router.delete(
    "/api/copies/{copy_id}",
    response_model=MessageResponse,
    summary="Delete a copy safely if unreferenced, or reject if loan history exists (librarian only)",
)
def delete_copy(
    copy_id: int,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Deletes an unreferenced copy record. Rejects deletion with 409 Conflict
    if historical loan records exist to preserve data integrity. Librarian only.
    """
    res = catalogue_service.delete_copy_service(db=db, copy_id=copy_id)
    return MessageResponse(message=res["detail"])
