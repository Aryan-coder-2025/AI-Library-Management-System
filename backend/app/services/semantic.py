"""
Semantic search and recommendation service layer.
Coordinates vector similarity ranking, pagination, recommendations, and embedding batch refreshes.
"""
from datetime import datetime
import math
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import semantic as crud_semantic
from app.database import atomic_write
from app.models import Book
from app.schemas import (
    BookRecommendationResponse,
    BookRecommendationResult,
    EmbeddingRefreshResponse,
    EmbeddingStatusResponse,
    SemanticBookResult,
    SemanticSearchResponse,
)
from app.services import embedding as embedding_service


# Concurrency state flag for background embedding operations
_is_refreshing_embeddings: bool = False


def semantic_search_service(
    db: Session,
    query: str,
    page: int = 1,
    page_size: int = 10,
    min_score: float = -1.0,
) -> SemanticSearchResponse:
    """
    Executes semantic book search using vector cosine similarity.
    Excludes archived books and books without usable embeddings.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return SemanticSearchResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            query="",
        )

    if len(cleaned_query) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query exceeds maximum allowed length of 500 characters.",
        )

    try:
        query_vector = embedding_service.encode_text(cleaned_query)
    except embedding_service.ModelUnavailableException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Semantic search model is unavailable: {str(e)}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}",
        ) from e

    # Retrieve non-archived books with embeddings
    candidate_books = crud_semantic.get_books_with_embeddings(db, include_archived=False)
    if not candidate_books:
        return SemanticSearchResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            query=cleaned_query,
        )

    # Compute similarity and rank
    scored_candidates: List[Tuple[Book, float]] = []
    for book in candidate_books:
        try:
            book_vec = embedding_service.deserialize_vector(book.embedding)
            score = embedding_service.compute_cosine_similarity(query_vector, book_vec)
            if score >= min_score:
                scored_candidates.append((book, score))
        except Exception:
            # Skip corrupted or incompatible vectors cleanly without crashing search
            continue

    # Sort descending by similarity score
    scored_candidates.sort(key=lambda x: x[1], reverse=True)

    total_count = len(scored_candidates)
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

    # Paginate
    offset = (page - 1) * page_size
    paged_slice = scored_candidates[offset : offset + page_size]

    paged_book_ids = [book.id for book, _ in paged_slice]
    total_map, avail_map = crud_semantic.get_copy_availability_maps(db, paged_book_ids)

    items: List[SemanticBookResult] = []
    for book, score in paged_slice:
        items.append(
            SemanticBookResult(
                id=book.id,
                title=book.title,
                author=book.author,
                isbn=book.isbn,
                category=book.category,
                description=book.description,
                total_copies=total_map.get(book.id, 0),
                available_copies=avail_map.get(book.id, 0),
                similarity_score=round(score, 4),
            )
        )

    return SemanticSearchResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        query=cleaned_query,
    )


def get_recommendations_service(
    db: Session,
    book_id: int,
    limit: int = 5,
) -> BookRecommendationResponse:
    """
    Computes content-based recommendations for a selected book using vector cosine similarity.
    Excludes the selected book itself and archived books.
    """
    source_book = crud_semantic.get_book_by_id(db, book_id)
    if not source_book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )

    if source_book.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate recommendations for an archived book.",
        )

    if source_book.embedding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected book does not have an embedding generated yet. Please generate embeddings first.",
        )

    if (
        source_book.embedding_updated_at is None
        or source_book.embedding_updated_at < source_book.updated_at
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected book has a stale embedding. Please refresh embeddings before requesting recommendations.",
        )

    try:
        source_vector = embedding_service.deserialize_vector(source_book.embedding)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Corrupted embedding on source book: {str(e)}",
        ) from e

    # Retrieve other active books with embeddings
    candidate_books = crud_semantic.get_books_with_embeddings(db, include_archived=False)

    scored_recs: List[Tuple[Book, float]] = []
    for book in candidate_books:
        if book.id == source_book.id:
            continue  # Exclude source book itself
        try:
            cand_vec = embedding_service.deserialize_vector(book.embedding)
            score = embedding_service.compute_cosine_similarity(source_vector, cand_vec)
            scored_recs.append((book, score))
        except Exception:
            continue

    # Sort descending by similarity score
    scored_recs.sort(key=lambda x: x[1], reverse=True)
    top_recs = scored_recs[:limit]

    recommendations = [
        BookRecommendationResult(
            id=b.id,
            title=b.title,
            author=b.author,
            isbn=b.isbn,
            category=b.category,
            description=b.description,
            similarity_score=round(score, 4),
        )
        for b, score in top_recs
    ]

    return BookRecommendationResponse(
        source_book_id=source_book.id,
        source_book_title=source_book.title,
        recommendations=recommendations,
        total=len(recommendations),
    )


def get_embedding_status_service(db: Session) -> EmbeddingStatusResponse:
    """Returns current embedding metrics and model availability status."""
    counts = crud_semantic.get_embedding_counts(db)
    model_avail = embedding_service.is_model_available()

    return EmbeddingStatusResponse(
        total_books=counts["total_books"],
        with_embedding=counts["with_embedding"],
        missing_embedding=counts["missing_embedding"],
        stale_embedding=counts["stale_embedding"],
        model_name=embedding_service.MODEL_NAME,
        model_available=model_avail,
        is_processing=_is_refreshing_embeddings,
    )


def refresh_embeddings_service(
    db: Session,
    force_refresh: bool = False,
) -> EmbeddingRefreshResponse:
    """
    Generates missing embeddings and updates stale ones.
    Librarian only operation.
    """
    global _is_refreshing_embeddings
    candidates = crud_semantic.get_books_needing_embedding(db, force_refresh=force_refresh)
    counts = crud_semantic.get_embedding_counts(db)

    if not candidates:
        return EmbeddingRefreshResponse(
            status="completed",
            total_candidates=0,
            processed=0,
            failed=0,
            stale=counts["stale_embedding"],
            missing=counts["missing_embedding"],
            message="All catalogue books already possess current embeddings.",
        )

    # Check model availability upfront
    if not embedding_service.is_model_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding model is unavailable. Please install dependencies or ensure weights are loaded.",
        )

    _is_refreshing_embeddings = True
    processed = 0
    failed = 0
    errors: List[str] = []

    try:
        for book in candidates:
            try:
                doc_text = embedding_service.build_book_document(
                    title=book.title,
                    author=book.author,
                    category=book.category,
                    description=book.description,
                )
                vec = embedding_service.encode_text(doc_text)
                raw_bytes = embedding_service.serialize_vector(vec)

                with atomic_write(db):
                    crud_semantic.save_book_embedding(db, book.id, raw_bytes)
                processed += 1
            except Exception as e:
                failed += 1
                errors.append(f"Book ID {book.id} ('{book.title}'): {str(e)}")

        updated_counts = crud_semantic.get_embedding_counts(db)
        return EmbeddingRefreshResponse(
            status="completed" if failed == 0 else "partial_failure",
            total_candidates=len(candidates),
            processed=processed,
            failed=failed,
            stale=updated_counts["stale_embedding"],
            missing=updated_counts["missing_embedding"],
            message=f"Generated {processed} embeddings ({failed} failures).",
            errors=errors,
        )
    finally:
        _is_refreshing_embeddings = False
