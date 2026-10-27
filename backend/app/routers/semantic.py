"""
Semantic search, recommendation, and embedding management API router.
Provides endpoints for AI-driven book discovery, similarity recommendations, and vector operations.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user, require_librarian
from app.models import User
from app.schemas import (
    BookRecommendationResponse,
    EmbeddingRefreshResponse,
    EmbeddingStatusResponse,
    SemanticSearchResponse,
)
from app.services import semantic as semantic_service

router = APIRouter(tags=["semantic"])


# ── Semantic Search ───────────────────────────────────────────────────────────

@router.get(
    "/api/search/semantic",
    response_model=SemanticSearchResponse,
    summary="Semantic book search using vector cosine similarity",
)
def semantic_search(
    q: str = Query(..., description="Query text to search across titles, authors, categories, and descriptions"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page (max 50)"),
    min_score: float = Query(-1.0, ge=-1.0, le=1.0, description="Minimum cosine similarity threshold"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Ranks non-archived catalogue books by vector cosine similarity against query embeddings.
    Available to students and librarians.
    """
    return semantic_service.semantic_search_service(
        db=db,
        query=q,
        page=page,
        page_size=page_size,
        min_score=min_score,
    )


# ── Content-Based Recommendations ─────────────────────────────────────────────

@router.get(
    "/api/books/{book_id}/recommendations",
    response_model=BookRecommendationResponse,
    summary="Retrieve content-based book recommendations for a selected book",
)
def get_book_recommendations(
    book_id: int,
    limit: int = Query(5, ge=1, le=20, description="Maximum number of recommendations (1 to 20)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Suggests similar, non-archived books based on vector cosine similarity with the selected book.
    Excludes the selected book itself. Content-based, not personalized.
    """
    return semantic_service.get_recommendations_service(
        db=db,
        book_id=book_id,
        limit=limit,
    )


# ── Embedding Management (Librarian Only) ─────────────────────────────────────

@router.get(
    "/api/embeddings/status",
    response_model=EmbeddingStatusResponse,
    summary="Retrieve embedding metrics and model status (librarian only)",
)
def get_embedding_status(
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """
    Returns counts of total, embedded, missing, and stale book embeddings,
    along with model availability status. Librarian only.
    """
    return semantic_service.get_embedding_status_service(db=db)


@router.post(
    "/api/embeddings/refresh",
    response_model=EmbeddingRefreshResponse,
    summary="Generate missing embeddings and refresh stale ones (librarian only)",
)
def refresh_embeddings(
    force_refresh: bool = Query(False, description="If True, recomputes embeddings for all books regardless of staleness"),
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Generates missing book embeddings and updates stale ones using the sentence-transformers model.
    Librarian only.
    """
    return semantic_service.refresh_embeddings_service(
        db=db,
        force_refresh=force_refresh,
    )
