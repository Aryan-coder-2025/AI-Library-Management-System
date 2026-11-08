"""
Book Waitlists & Holds Router (CIRC-02).
Provides patron hold placement, self-service queue monitoring, hold cancellation,
and librarian queue administration.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_write_db
from app.dependencies import get_current_active_user, require_librarian
from app.models import User
from app.schemas import BookHoldCreateRequest, BookHoldListResponse, BookHoldResponse
from app.services.holds import (
    cancel_hold_service,
    get_librarian_holds_service,
    get_my_holds_service,
    place_hold_service,
    sweep_expired_holds_service,
)

router = APIRouter(prefix="/api/holds", tags=["Book Holds & Waitlists"])


@router.post("", response_model=BookHoldResponse, status_code=status.HTTP_201_CREATED, summary="Place a hold on a checked-out book")
def place_hold(
    hold_in: BookHoldCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Places an authenticated student or teacher patron on the waitlist for a monograph.
    Permitted only when no available copies are on library shelves.
    """
    return place_hold_service(db, current_user, hold_in.book_id)


@router.get("/me", response_model=BookHoldListResponse, summary="View patron active and historical holds")
def get_my_holds(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """Returns all holds belonging to the authenticated patron with live FIFO queue positions."""
    return get_my_holds_service(db, current_user.id)


@router.post("/{hold_id}/cancel", response_model=BookHoldResponse, summary="Cancel an active book hold")
def cancel_hold(
    hold_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Cancels a waiting or ready-for-pickup hold.
    If a physical copy was allocated to this hold, it is automatically reallocated to the next patron in queue.
    """
    return cancel_hold_service(db, current_user, hold_id)


@router.get("", response_model=BookHoldListResponse, summary="Librarian hold queue oversight")
def get_librarian_holds(
    status: Optional[str] = Query(None, description="Filter by hold status (waiting, ready_for_pickup, fulfilled, cancelled, expired)"),
    book_id: Optional[int] = Query(None, description="Filter by book ID"),
    librarian: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Staff endpoint to inspect hold queues and patron allocations."""
    return get_librarian_holds_service(db, status_filter=status, book_id=book_id)


@router.post("/sweep", summary="Sweep and expire overdue uncollected holds")
def sweep_expired_holds(
    librarian: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Staff maintenance endpoint to expire uncollected holds and advance waitlist queues."""
    expired_count = sweep_expired_holds_service(db)
    return {"message": f"Successfully swept {expired_count} expired holds."}

