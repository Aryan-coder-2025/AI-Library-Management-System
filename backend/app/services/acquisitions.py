"""
Acquisition Workflow & Search Demand Analytics Service (INTEL-05).
Extracts demand signals from zero-result patron search telemetry and provides
a controlled librarian-managed review and triage pipeline without automated billing.
"""
from datetime import datetime
import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import atomic_write
from app.models import AcquisitionRequest, SearchEvent, User
from app.schemas import (
    AcquisitionRequestCreate,
    AcquisitionRequestListResponse,
    AcquisitionRequestResponse,
    AcquisitionRequestUpdate,
    AcquisitionSuggestion,
    AcquisitionSuggestionListResponse,
)

logger = logging.getLogger("athenaeum.acquisitions")


def serialize_acquisition_request(req: AcquisitionRequest) -> AcquisitionRequestResponse:
    """Serializes AcquisitionRequest model to schema."""
    return AcquisitionRequestResponse(
        id=req.id,
        suggested_title=req.suggested_title,
        suggested_author=req.suggested_author,
        isbn=req.isbn,
        search_query_origin=req.search_query_origin,
        frequency_score=req.frequency_score,
        status=req.status,
        requested_by_id=req.requested_by_id,
        reviewed_by_id=req.reviewed_by_id,
        reviewer_notes=req.reviewer_notes,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def get_acquisition_suggestions_service(db: Session, limit: int = 25) -> AcquisitionSuggestionListResponse:
    """
    Identifies high-frequency zero-result search events to reveal unmet patron demand.
    Aggregates by normalized query string to generate prospective acquisition candidates.
    """
    results = db.execute(
        select(
            func.lower(SearchEvent.query_text).label("norm_query"),
            func.count(SearchEvent.id).label("freq"),
            func.min(SearchEvent.executed_at).label("first_seen"),
            func.max(SearchEvent.executed_at).label("last_seen"),
        )
        .where(SearchEvent.results_count == 0)
        .group_by(func.lower(SearchEvent.query_text))
        .order_by(func.count(SearchEvent.id).desc())
        .limit(limit)
    ).all()

    total_zero = db.execute(
        select(func.count(SearchEvent.id)).where(SearchEvent.results_count == 0)
    ).scalar() or 0

    suggestions = [
        AcquisitionSuggestion(
            query_text=row.norm_query,
            frequency=row.freq,
            first_searched=row.first_seen,
            last_searched=row.last_seen,
        )
        for row in results
    ]

    return AcquisitionSuggestionListResponse(
        suggestions=suggestions,
        total_zero_result_queries=total_zero,
    )


def create_acquisition_request_service(
    db: Session,
    user: User,
    req: AcquisitionRequestCreate,
) -> AcquisitionRequestResponse:
    """Creates a new acquisition request candidate for collection development review."""
    with atomic_write(db):
        now = datetime.utcnow()
        new_req = AcquisitionRequest(
            suggested_title=req.title.strip(),
            suggested_author=req.author.strip() if req.author else None,
            isbn=req.isbn.strip() if req.isbn else None,
            search_query_origin=req.search_query_origin.strip() if req.search_query_origin else None,
            frequency_score=1,
            status="suggested",
            requested_by_id=user.id,
            reviewer_notes=req.notes.strip() if req.notes else None,
            created_at=now,
            updated_at=now,
        )
        db.add(new_req)
        db.flush()
        db.refresh(new_req)

        return serialize_acquisition_request(new_req)


def update_acquisition_request_service(
    db: Session,
    librarian: User,
    request_id: int,
    req: AcquisitionRequestUpdate,
) -> AcquisitionRequestResponse:
    """Reviews and advances acquisition status ('approved', 'rejected', 'ordered', 'received')."""
    if librarian.role != "librarian":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only librarians can review and advance acquisition requests.",
        )

    with atomic_write(db):
        acq = db.execute(select(AcquisitionRequest).where(AcquisitionRequest.id == request_id)).scalar_one_or_none()
        if not acq:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acquisition request not found.")

        now = datetime.utcnow()
        acq.status = req.status
        acq.reviewed_by_id = librarian.id
        if req.reviewer_notes:
            acq.reviewer_notes = req.reviewer_notes.strip()
        acq.updated_at = now

        db.add(acq)
        db.flush()
        db.refresh(acq)

        return serialize_acquisition_request(acq)


def list_acquisition_requests_service(
    db: Session,
    status_filter: Optional[str] = None,
) -> AcquisitionRequestListResponse:
    """Lists acquisition requests with optional status filtering."""
    query = select(AcquisitionRequest)
    if status_filter:
        query = query.where(AcquisitionRequest.status == status_filter.strip().lower())

    requests = db.execute(query.order_by(AcquisitionRequest.updated_at.desc())).scalars().all()
    items = [serialize_acquisition_request(r) for r in requests]
    return AcquisitionRequestListResponse(items=items, total=len(items))

