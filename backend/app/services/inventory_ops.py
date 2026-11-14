"""
Inventory Operations & Audit Logging Service (CIRC-07).
Handles lost and damaged copy processing, status updates, maintenance transitions,
and full auditable event histories without financial/fine assessments.
"""
from datetime import datetime
import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import atomic_write
from app.models import BookCopy, BookHold, InventoryEvent, User
from app.schemas import InventoryEventResponse
from app.services.holds import advance_queue_for_copy

logger = logging.getLogger("athenaeum.inventory.ops")


def serialize_inventory_event(event: InventoryEvent) -> InventoryEventResponse:
    """Serializes an InventoryEvent model into schema."""
    auditor_name = event.auditor.full_name if event.auditor else "System"
    copy_code = event.copy.copy_code if event.copy else "UNKNOWN"
    book_title = event.copy.book.title if (event.copy and event.copy.book) else "Unknown Monograph"

    return InventoryEventResponse(
        id=event.id,
        copy_id=event.copy_id,
        copy_code=copy_code,
        book_title=book_title,
        auditor_id=event.auditor_id,
        auditor_name=auditor_name,
        event_type=event.event_type,
        previous_status=event.previous_status,
        new_status=event.new_status,
        notes=event.notes,
        recorded_at=event.recorded_at,
    )


def process_copy_status_change(
    db: Session,
    librarian: User,
    copy_id: int,
    new_status: str,
    notes: Optional[str] = None,
) -> InventoryEventResponse:
    """
    Updates operational status of a physical copy (available, maintenance, lost, damaged, retired)
    and logs an auditable InventoryEvent.
    If the copy is currently reserved on hold and transitioned away from available,
    it reallocates another copy or returns the hold to waiting.
    """
    if librarian.role != "librarian":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only librarians can update copy operational status and record inventory audits.",
        )

    clean_status = new_status.strip().lower()
    if clean_status not in ("available", "maintenance", "lost", "damaged", "retired", "in_reshelving"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid copy status '{clean_status}'.",
        )

    with atomic_write(db):
        copy = db.execute(select(BookCopy).where(BookCopy.id == copy_id)).scalar_one_or_none()
        if not copy:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical book copy not found.")

        prev_status = copy.operational_status
        if prev_status == clean_status and not notes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Copy is already in '{clean_status}' status.",
            )

        now = datetime.utcnow()

        # If copy was allocated to a ready_for_pickup hold and is no longer available:
        if clean_status != "available":
            allocated_hold = db.execute(
                select(BookHold).where(
                    BookHold.copy_id == copy.id,
                    BookHold.status == "ready_for_pickup",
                )
            ).scalar_one_or_none()

            if allocated_hold:
                logger.info(
                    "Copy %s marked %s while allocated to hold %s; releasing allocation",
                    copy.id, clean_status, allocated_hold.id,
                )
                allocated_hold.copy_id = None
                allocated_hold.status = "waiting"
                allocated_hold.allocated_at = None
                allocated_hold.pickup_expires_at = None
                db.add(allocated_hold)
                # Try to reallocate another available shelf copy
                advance_queue_for_copy(db, copy_id=None, book_id=copy.book_id)

        copy.operational_status = clean_status
        if notes:
            copy.notes = notes.strip()
        db.add(copy)

        # Audit event type
        if clean_status == "lost":
            event_type = "loss_reported"
        elif clean_status == "damaged":
            event_type = "damage_flagged"
        elif prev_status in ("lost", "damaged", "maintenance") and clean_status == "available":
            event_type = "reinstated"
        else:
            event_type = "status_change"

        event = InventoryEvent(
            copy_id=copy.id,
            auditor_id=librarian.id,
            event_type=event_type,
            previous_status=prev_status,
            new_status=clean_status,
            notes=notes.strip() if notes else None,
            recorded_at=now,
        )
        db.add(event)
        db.flush()
        db.refresh(event)

        return serialize_inventory_event(event)


def get_copy_audit_history(db: Session, copy_id: int) -> List[InventoryEventResponse]:
    """Retrieves chronological audit events for a physical book copy."""
    copy = db.execute(select(BookCopy).where(BookCopy.id == copy_id)).scalar_one_or_none()
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical book copy not found.")

    events = db.execute(
        select(InventoryEvent)
        .where(InventoryEvent.copy_id == copy_id)
        .order_by(InventoryEvent.recorded_at.desc())
    ).scalars().all()

    return [serialize_inventory_event(e) for e in events]

