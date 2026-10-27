"""
Semantic search and embedding CRUD operations.
Handles database queries for vector retrieval, candidate filtering, and embedding storage.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Book, BookCopy, Loan


def get_books_with_embeddings(
    db: Session,
    include_archived: bool = False,
    include_stale: bool = False,
) -> List[Book]:
    """
    Retrieves candidate books for semantic search and recommendation operations.
    Archived books are excluded by default.
    Stale embeddings (where embedding_updated_at is null or older than updated_at)
    are excluded by default from ordinary semantic search and recommendations.
    """
    stmt = select(Book).where(
        Book.embedding.is_not(None),
        Book.embedding_updated_at.is_not(None),
    )
    if not include_archived:
        stmt = stmt.where(Book.is_archived.is_(False))
    if not include_stale:
        stmt = stmt.where(Book.embedding_updated_at >= Book.updated_at)
    return list(db.execute(stmt).scalars().all())


def get_book_by_id(db: Session, book_id: int) -> Optional[Book]:
    """Retrieves a single book by ID."""
    return db.execute(select(Book).where(Book.id == book_id)).scalar_one_or_none()


def get_embedding_counts(db: Session) -> dict:
    """
    Computes summary metrics for book embeddings:
    - total_books (non-archived)
    - with_embedding
    - missing_embedding
    - stale_embedding (books updated after embedding_updated_at or embedding_updated_at is null)
    """
    base_query = select(Book).where(Book.is_archived.is_(False))
    total_books = db.execute(select(func.count(Book.id)).where(Book.is_archived.is_(False))).scalar() or 0

    with_embedding = db.execute(
        select(func.count(Book.id)).where(
            Book.is_archived.is_(False),
            Book.embedding.is_not(None),
        )
    ).scalar() or 0

    missing_embedding = db.execute(
        select(func.count(Book.id)).where(
            Book.is_archived.is_(False),
            Book.embedding.is_(None),
        )
    ).scalar() or 0

    stale_embedding = db.execute(
        select(func.count(Book.id)).where(
            Book.is_archived.is_(False),
            Book.embedding.is_not(None),
            or_(
                Book.embedding_updated_at.is_(None),
                Book.embedding_updated_at < Book.updated_at,
            ),
        )
    ).scalar() or 0

    return {
        "total_books": total_books,
        "with_embedding": with_embedding,
        "missing_embedding": missing_embedding,
        "stale_embedding": stale_embedding,
    }


def get_books_needing_embedding(
    db: Session,
    force_refresh: bool = False,
) -> List[Book]:
    """
    Retrieves candidate books for embedding generation:
    - If force_refresh is True: all active books.
    - If False: active books with missing or stale embeddings.
    """
    if force_refresh:
        stmt = select(Book).where(Book.is_archived.is_(False)).order_by(Book.id.asc())
    else:
        stmt = (
            select(Book)
            .where(
                Book.is_archived.is_(False),
                or_(
                    Book.embedding.is_(None),
                    Book.embedding_updated_at.is_(None),
                    Book.embedding_updated_at < Book.updated_at,
                ),
            )
            .order_by(Book.id.asc())
        )
    return list(db.execute(stmt).scalars().all())


def save_book_embedding(
    db: Session,
    book_id: int,
    embedding_bytes: bytes,
) -> bool:
    """
    Updates a book's embedding vector and timestamp without modifying its metadata updated_at timestamp.
    Ensures embedding_updated_at is consistent with the current metadata version.
    """
    book = db.execute(select(Book).where(Book.id == book_id)).scalar_one_or_none()
    if not book:
        return False
    current_updated_at = book.updated_at
    now = datetime.utcnow()
    emb_timestamp = max(now, current_updated_at) if current_updated_at else now

    book.embedding = embedding_bytes
    book.embedding_updated_at = emb_timestamp
    if current_updated_at:
        book.updated_at = current_updated_at
    db.add(book)
    db.flush()
    db.refresh(book)
    return True


def get_copy_availability_maps(
    db: Session,
    book_ids: List[int],
) -> Tuple[Dict[int, int], Dict[int, int]]:
    """
    Returns total and available copy counts for a list of book IDs,
    reusing the optimized grouped aggregation logic.
    """
    if not book_ids:
        return {}, {}

    total_stmt = (
        select(BookCopy.book_id, func.count(BookCopy.id).label("total_count"))
        .where(BookCopy.book_id.in_(book_ids))
        .group_by(BookCopy.book_id)
    )
    total_map: Dict[int, int] = dict(db.execute(total_stmt).all())

    active_loans_subq = (
        select(Loan.copy_id)
        .where(Loan.returned_at.is_(None))
        .scalar_subquery()
    )

    avail_stmt = (
        select(BookCopy.book_id, func.count(BookCopy.id).label("avail_count"))
        .where(
            BookCopy.book_id.in_(book_ids),
            BookCopy.operational_status == "available",
            BookCopy.id.not_in(active_loans_subq),
        )
        .group_by(BookCopy.book_id)
    )
    avail_map: Dict[int, int] = dict(db.execute(avail_stmt).all())

    return total_map, avail_map
