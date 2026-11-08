"""
FastAPI Router for Circulation Operations: QR Collection & Lost/Damaged Processing (CIRC-03, CIRC-07).
"""
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_user, require_librarian
from app.models import User
from app.schemas import (
    BookCollectionPassResponse,
    BookCollectionVerifyRequest,
    BookCollectionVerifyResponse,
    CopyStatusUpdateRequest,
    InventoryEventListResponse,
    InventoryEventResponse,
)
from app.services.inventory_ops import get_copy_audit_history, process_copy_status_change
from app.services.qr_collection import generate_book_collection_pass, verify_and_fulfill_qr_collection

router = APIRouter(prefix="/api/circulation", tags=["Circulation Operations & Collections"])


@router.post(
    "/qr-collection/pass/{hold_id}",
    response_model=BookCollectionPassResponse,
    summary="Generate QR book collection pass",
)
def get_qr_collection_pass(
    hold_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Generates a secure, single-use QR collection pass for a patron with a ready hold."""
    return generate_book_collection_pass(db, current_user, hold_id)


@router.post(
    "/qr-collection/verify",
    response_model=BookCollectionVerifyResponse,
    summary="Verify QR collection pass and issue loan",
)
def verify_qr_collection(
    req: BookCollectionVerifyRequest,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Circulation desk endpoint to scan and verify patron collection pass, issuing the loan."""
    return verify_and_fulfill_qr_collection(db, current_user, req.token)


@router.post(
    "/copies/{copy_id}/status",
    response_model=InventoryEventResponse,
    summary="Update copy operational status with audit log",
)
def update_copy_status(
    copy_id: int,
    req: CopyStatusUpdateRequest,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Marks physical copy as available, maintenance, lost, damaged, or retired with auditable notes."""
    return process_copy_status_change(db, current_user, copy_id, req.status, req.notes)


@router.get(
    "/copies/{copy_id}/audit-history",
    response_model=InventoryEventListResponse,
    summary="Get copy audit history",
)
def get_copy_history(
    copy_id: int,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Retrieves chronological inventory audit history for a physical copy."""
    events = get_copy_audit_history(db, copy_id)
    return InventoryEventListResponse(items=events, total=len(events))

