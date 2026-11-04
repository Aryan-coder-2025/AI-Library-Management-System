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
    HybridBookResult,
    HybridSearchResponse,
    SemanticBookResult,
    SemanticSearchResponse,
)
from app.services import embedding as embedding_service
from app.services.isbn import parse_and_normalize_isbn


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


def hybrid_search_service(
    db: Session,
    query: str,
    page: int = 1,
    page_size: int = 10,
    category: Optional[str] = None,
    min_score: float = -1.0,
    include_archived: bool = False,
    candidate_limit: int = 100,
) -> HybridSearchResponse:
    """
    Executes dual-channel hybrid search combining:
    1. Parameterized multi-token lexical candidate retrieval.
    2. Dense semantic vector similarity ranking (sentence-transformers/all-MiniLM-L6-v2).
    3. Exact identifier (ISBN-10, ISBN-13, exact title) prioritization.
    4. Reciprocal Rank Fusion (RRF, k=60) with deterministic tie-breaking.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return HybridSearchResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            total_lexical_matches=0,
            total_semantic_matches=0,
            total_fused_candidates=0,
            query="",
            applied_category=category,
        )

    if len(cleaned_query) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query exceeds maximum allowed length of 500 characters.",
        )

    # 1. Exact Identifier Extraction (ISBN-10 / ISBN-13)
    clean_isbn13 = parse_and_normalize_isbn(cleaned_query)

    # 2. Channel 1: Lexical Candidate Retrieval
    lexical_candidates, total_lexical_matches = crud_semantic.get_lexical_candidates(
        db=db,
        query=cleaned_query,
        category=category,
        include_archived=include_archived,
        limit=candidate_limit,
        exact_isbn_clean=clean_isbn13,
    )

    lexical_rank_map = {
        book.id: rank_idx + 1
        for rank_idx, (book, _score) in enumerate(lexical_candidates)
    }

    # 3. Channel 2: Dense Semantic Vector Candidate Retrieval
    candidate_books = crud_semantic.get_books_with_embeddings(
        db=db,
        include_archived=include_archived,
        include_stale=False,
    )
    if category and category.strip():
        cat_lower = category.strip().lower()
        candidate_books = [b for b in candidate_books if b.category.lower() == cat_lower]

    semantic_candidates: List[Tuple[Book, float]] = []
    semantic_rank_map = {}
    semantic_score_map = {}
    total_semantic_matches = 0

    if candidate_books and embedding_service.is_model_available():
        try:
            query_vector = embedding_service.encode_text(cleaned_query)
            scored_semantic = []
            for book in candidate_books:
                try:
                    book_vec = embedding_service.deserialize_vector(book.embedding)
                    sim = embedding_service.compute_cosine_similarity(query_vector, book_vec)
                    if sim >= min_score:
                        scored_semantic.append((book, sim))
                except Exception:
                    continue

            scored_semantic.sort(key=lambda x: x[1], reverse=True)
            total_semantic_matches = len(scored_semantic)
            semantic_candidates = scored_semantic[:candidate_limit]

            for rank_idx, (book, sim) in enumerate(semantic_candidates):
                semantic_rank_map[book.id] = rank_idx + 1
                semantic_score_map[book.id] = sim

            # Record scores for un-truncated matches as well
            for book, sim in scored_semantic:
                if book.id not in semantic_score_map:
                    semantic_score_map[book.id] = sim

        except Exception:
            # Graceful degradation if model inference fails
            pass

    # 4. Candidate Pool Union & Deduplication
    all_books_dict = {}
    for book, _ in lexical_candidates:
        all_books_dict[book.id] = book
    for book, _ in semantic_candidates:
        all_books_dict[book.id] = book

    # 5. Reciprocal Rank Fusion (RRF) & Tie-Breaking
    RRF_K = 60.0
    clean_query_lower = cleaned_query.lower()

    fused_candidates = []
    for b_id, book in all_books_dict.items():
        lex_rank = lexical_rank_map.get(b_id)
        sem_rank = semantic_rank_map.get(b_id)
        sim_score = semantic_score_map.get(b_id)

        rrf_score = 0.0
        channels = []
        if lex_rank is not None:
            rrf_score += 1.0 / (RRF_K + lex_rank)
            channels.append("lexical")
        if sem_rank is not None:
            rrf_score += 1.0 / (RRF_K + sem_rank)
            channels.append("semantic")

        # Exact identifier detection
        book_isbn_clean = book.isbn.replace("-", "").replace(" ", "").upper() if book.isbn else ""
        is_exact_isbn = bool(clean_isbn13 and book_isbn_clean == clean_isbn13)
        if is_exact_isbn:
            channels = ["exact_identifier"]
            rrf_score = 10.0  # Dominant priority for exact ISBN point match

        is_exact_title = bool(clean_query_lower and book.title.strip().lower() == clean_query_lower)

        fused_candidates.append({
            "book": book,
            "rrf_score": rrf_score,
            "lexical_rank": lex_rank,
            "semantic_rank": sem_rank,
            "similarity_score": round(sim_score, 4) if sim_score is not None else None,
            "match_channels": channels,
            "is_exact_isbn": is_exact_isbn,
            "is_exact_title": is_exact_title,
        })

    # Sort using deterministic 5-tuple tie-breaker:
    # 1. Exact ISBN point match (1 or 0)
    # 2. Exact Title match (1 or 0)
    # 3. RRF Score descending
    # 4. Semantic similarity score descending
    # 5. Book ID ascending
    fused_candidates.sort(
        key=lambda x: (
            1 if x["is_exact_isbn"] else 0,
            1 if x["is_exact_title"] else 0,
            x["rrf_score"],
            x["similarity_score"] if x["similarity_score"] is not None else -2.0,
            -x["book"].id,
        ),
        reverse=True,
    )

    total_fused = len(fused_candidates)
    total_pages = math.ceil(total_fused / page_size) if total_fused > 0 else 0

    # 6. Pagination & Availability Enrichment
    offset = (page - 1) * page_size
    paged_slice = fused_candidates[offset : offset + page_size]

    paged_book_ids = [item["book"].id for item in paged_slice]
    total_map, avail_map = crud_semantic.get_copy_availability_maps(db, paged_book_ids)

    items: List[HybridBookResult] = []
    for item in paged_slice:
        b = item["book"]
        items.append(
            HybridBookResult(
                id=b.id,
                title=b.title,
                author=b.author,
                isbn=b.isbn,
                category=b.category,
                description=b.description,
                total_copies=total_map.get(b.id, 0),
                available_copies=avail_map.get(b.id, 0),
                rrf_score=round(item["rrf_score"], 6),
                lexical_rank=item["lexical_rank"],
                semantic_rank=item["semantic_rank"],
                similarity_score=item["similarity_score"],
                match_channels=item["match_channels"],
            )
        )

    return HybridSearchResponse(
        items=items,
        total=total_fused,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        total_lexical_matches=total_lexical_matches,
        total_semantic_matches=total_semantic_matches,
        total_fused_candidates=total_fused,
        query=cleaned_query,
        applied_category=category,
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
