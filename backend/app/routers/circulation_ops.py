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
    BookReturnDischargeRequest,
    BookReturnDischargeResponse,
    BookReturnPassResponse,
    BookReturnReceiptResponse,
    BookReturnTokenItemResponse,
    CirculationClearanceResponse,
    CopyStatusUpdateRequest,
    InventoryEventListResponse,
    InventoryEventResponse,
    ExitGateVerificationRequest,
    ExitGateVerificationResponse,
)
from app.services import shelf_locator
from app.services.inventory_ops import get_copy_audit_history, process_copy_status_change
from app.services.qr_collection import generate_book_collection_pass, verify_and_fulfill_qr_collection
from app.services.qr_return import (
    cancel_book_return_token,
    generate_book_return_token,
    get_patron_clearance_status_service,
    get_pending_return_tokens_service,
    get_return_receipt_service,
    verify_and_discharge_qr_return,
)

router = APIRouter(prefix="/api/circulation", tags=["Circulation Operations & Collections"])


# ── Return Clearance & Loan Discharge Endpoints ───────────────────────────────

@router.post(
    "/qr-return/pass/{loan_id}",
    response_model=BookReturnPassResponse,
    summary="Generate QR book return token pass",
)
def get_qr_return_pass(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Generates an official return clearance token and QR payload for an active loan."""
    return generate_book_return_token(db, current_user, loan_id)


@router.post(
    "/qr-return/cancel/{loan_id}",
    summary="Cancel active in-flight return pass",
)
def cancel_qr_return_pass(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Cancels an active return token if the student decides to keep studying with the book."""
    return cancel_book_return_token(db, current_user, loan_id)


@router.post(
    "/qr-return/discharge",
    response_model=BookReturnDischargeResponse,
    summary="Verify return token and discharge loan at circulation desk",
)
def verify_qr_return_discharge(
    req: BookReturnDischargeRequest,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Circulation desk endpoint to scan/verify return token, assess condition, and discharge loan."""
    return verify_and_discharge_qr_return(
        db=db,
        librarian=current_user,
        token_str=req.token,
        condition=req.condition,
        condition_notes=req.condition_notes,
    )


@router.get(
    "/qr-return/pending",
    response_model=List[BookReturnTokenItemResponse],
    summary="List active in-flight return passes awaiting check-in",
)
def get_pending_returns(
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Librarian queue endpoint to inspect active return tokens issued to students."""
    return get_pending_return_tokens_service(db)


@router.get(
    "/receipt/{loan_id}",
    response_model=BookReturnReceiptResponse,
    summary="Get official printable digital return clearance receipt",
)
def get_return_receipt(
    loan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves official digital return receipt slip for a discharged loan."""
    return get_return_receipt_service(db, current_user, loan_id)


@router.get(
    "/clearance/my-status",
    response_model=CirculationClearanceResponse,
    summary="Get patron circulation clearance / No Dues status",
)
def get_patron_clearance_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Computes institutional library clearance status.
    Non-punitive: Shows positive clearance certificate or friendly advisory notice.
    """
    return get_patron_clearance_status_service(db, current_user)


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


# ── Physical Exit Security & Anti-Theft Sensor Endpoints ─────────────────────

@router.post(
    "/verify-exit-gate",
    response_model=ExitGateVerificationResponse,
    summary="Simulate or query physical RFID/EM anti-theft security exit gate",
)
def verify_exit_gate(
    req: ExitGateVerificationRequest,
    db: Session = Depends(get_write_db),
):
    """
    Automated exit gate check: Evaluates if a physical book copy passing the RFID exit gate
    has an active loan or triggers the security theft alarm.
    """
    return shelf_locator.verify_exit_gate_service(db=db, copy_code=req.copy_code)


@router.get(
    "/verify-exit-gate/{copy_code}",
    response_model=ExitGateVerificationResponse,
    summary="Fast query for exit security gate sensor hardware",
)
def verify_exit_gate_by_code(
    copy_code: str,
    db: Session = Depends(get_write_db),
):
    """Hardware wedge query for exit security gate controllers."""
    return shelf_locator.verify_exit_gate_service(db=db, copy_code=copy_code)

