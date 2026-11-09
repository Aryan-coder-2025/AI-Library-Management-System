"""
QR Book Return & Loan Discharge Service.
Coordinates patron return token issuance, circulation desk check-in verification,
physical copy condition assessment, automatic waitlist reallocation, and digital return receipts.
"""
from datetime import date, datetime, timedelta
import hashlib
import logging
import secrets
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import atomic_write
from app.models import BookCopy, BookReturnToken, InventoryEvent, Loan, Notification, User
from app.schemas import (
    BookReturnDischargeResponse,
    BookReturnPassResponse,
    BookReturnReceiptResponse,
    BookReturnTokenItemResponse,
    CirculationClearanceResponse,
)
from app.services.holds import advance_queue_for_copy
from app.utils.date import get_utc_today

logger = logging.getLogger("athenaeum.circulation.return")


def hash_return_token(token: str) -> str:
    """Computes deterministic SHA-256 hash of return token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_book_return_token(db: Session, user: User, loan_id: int) -> BookReturnPassResponse:
    """
    Generates a secure return clearance token and QR payload for an active loan.
    Invalidates previous unused return tokens for the same loan.
    """
    with atomic_write(db):
        loan = db.execute(select(Loan).where(Loan.id == loan_id)).scalar_one_or_none()
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan record not found.")

        # Patrons can only generate return tokens for their own loans; librarians can for any
        if user.role != "librarian" and loan.student_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to initiate return for this loan.",
            )

        if loan.returned_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This loan has already been returned and discharged.",
            )

        now = datetime.utcnow()

        # Invalidate existing unused return tokens for this loan
        active_tokens = db.execute(
            select(BookReturnToken).where(
                BookReturnToken.loan_id == loan.id,
                BookReturnToken.is_used == False,
            )
        ).scalars().all()
        for t in active_tokens:
            t.is_used = True
            t.used_at = now

        # Generate clean unique numeric code (6 digits, e.g. RET-849201)
        while True:
            token_num = secrets.randbelow(900000) + 100000
            raw_code = f"RET-{token_num}"
            raw_token = f"ATN-RETURN-{token_num}"
            token_hash = hash_return_token(raw_token)
            existing = db.execute(
                select(BookReturnToken).where(BookReturnToken.token_hash == token_hash)
            ).scalar_one_or_none()
            if not existing:
                break

        receipt_code = f"REC-{token_num}"
        expires_at = now + timedelta(days=7)

        token_record = BookReturnToken(
            loan_id=loan.id,
            user_id=loan.student_id,
            token_hash=token_hash,
            raw_code=raw_code,
            receipt_code=receipt_code,
            created_at=now,
            expires_at=expires_at,
            is_used=False,
        )
        db.add(token_record)
        db.flush()

        copy = loan.copy
        book = copy.book if copy else None

        return BookReturnPassResponse(
            loan_id=loan.id,
            copy_id=loan.copy_id,
            copy_code=copy.copy_code if copy else "COPY",
            book_id=book.id if book else 0,
            book_title=book.title if book else "Monograph",
            book_author=book.author if book else None,
            patron_id=loan.student_id,
            patron_name=loan.student.full_name if loan.student else "Patron",
            raw_code=raw_code,
            token=raw_token,
            qr_payload=f"ATHENAEUM-RETURN:{raw_token}",
            expires_at=expires_at,
        )


def cancel_book_return_token(db: Session, user: User, loan_id: int) -> dict:
    """Cancels an active in-flight return token if the student decides to keep studying."""
    with atomic_write(db):
        loan = db.execute(select(Loan).where(Loan.id == loan_id)).scalar_one_or_none()
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan record not found.")

        if user.role != "librarian" and loan.student_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

        now = datetime.utcnow()
        active_tokens = db.execute(
            select(BookReturnToken).where(
                BookReturnToken.loan_id == loan.id,
                BookReturnToken.is_used == False,
            )
        ).scalars().all()

        for t in active_tokens:
            t.is_used = True
            t.used_at = now

        return {"message": "Return pass cancelled successfully. Your loan remains active."}


def verify_and_discharge_qr_return(
    db: Session,
    librarian: User,
    token_str: str,
    condition: str = "good",
    condition_notes: Optional[str] = None,
) -> BookReturnDischargeResponse:
    """
    Circulation desk verification of patron's return token.
    Atomically discharges the loan, assesses physical copy condition,
    logs any condition damage, and reallocates the copy to the waitlist if applicable.
    """
    if librarian.role != "librarian":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only librarians can discharge loans at the circulation desk.",
        )

    clean_token = token_str.strip()
    if clean_token.startswith("ATHENAEUM-RETURN:"):
        clean_token = clean_token.replace("ATHENAEUM-RETURN:", "", 1).strip()

    # Generate candidate variations
    candidates = [clean_token]
    upper_tok = clean_token.upper()
    if upper_tok not in candidates:
        candidates.append(upper_tok)
    if upper_tok.startswith("RET-"):
        num_part = upper_tok.replace("RET-", "", 1).strip()
        candidates.append(f"ATN-RETURN-{num_part}")
        candidates.append(num_part)
    elif upper_tok.startswith("ATN-RETURN-"):
        num_part = upper_tok.replace("ATN-RETURN-", "", 1).strip()
        candidates.append(num_part)
        candidates.append(f"RET-{num_part}")
    elif upper_tok.isdigit():
        candidates.append(f"ATN-RETURN-{upper_tok}")
        candidates.append(f"RET-{upper_tok}")

    with atomic_write(db):
        token_record = None
        for cand in candidates:
            cand_hash = hash_return_token(cand)
            token_record = db.execute(
                select(BookReturnToken).where(BookReturnToken.token_hash == cand_hash)
            ).scalar_one_or_none()
            if not token_record:
                # Also try matching raw_code
                token_record = db.execute(
                    select(BookReturnToken).where(BookReturnToken.raw_code == cand)
                ).scalar_one_or_none()
            if token_record:
                break

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid return clearance token '{clean_token}'. Token not recognized or already consumed.",
            )

        if token_record.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This return token has already been consumed and discharged.",
            )

        now = datetime.utcnow()
        if token_record.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This return token has expired. Please ask the patron to generate a new pass.",
            )

        loan = token_record.loan
        if not loan or loan.returned_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Loan is no longer active or has already been returned.",
            )

        # 1. Discharge loan
        loan.returned_at = now
        token_record.is_used = True
        token_record.used_at = now
        token_record.condition = condition
        token_record.condition_notes = condition_notes
        token_record.discharged_by_id = librarian.id
        db.add(loan)
        db.add(token_record)

        copy = loan.copy
        book = copy.book if copy else None
        book_title = book.title if book else "Monograph"
        copy_code = copy.copy_code if copy else "COPY"
        patron_name = loan.student.full_name if loan.student else f"Patron #{loan.student_id}"

        # 2. Update copy condition & operational status
        waitlist_advanced = False
        if condition == "maintenance":
            copy.operational_status = "maintenance"
            event = InventoryEvent(
                copy_id=copy.id,
                event_type="status_change",
                from_status="available",
                to_status="maintenance",
                reason=f"Returned with damage/wear: {condition_notes or 'Requires physical repair'}",
                performed_by_id=librarian.id,
                created_at=now,
            )
            db.add(copy)
            db.add(event)
            logger.info("Copy %s returned with maintenance flag by librarian %s", copy.id, librarian.id)
        else:
            copy.operational_status = "available"
            db.add(copy)
            # Reallocate to waitlist if another student is waiting
            next_hold = advance_queue_for_copy(db, copy.book_id, copy.id)
            if next_hold:
                waitlist_advanced = True

        # 3. Create digital receipt notification for patron
        community_note = " Your copy was immediately reallocated to the next student in queue!" if waitlist_advanced else ""
        notification = Notification(
            user_id=loan.student_id,
            notification_type="loan_returned",
            title="Loan Discharged & Return Confirmed",
            message=(
                f"Your loan for '{book_title}' (Copy #{copy_code}) has been successfully discharged and cleared on "
                f"{now.strftime('%b %d, %Y')}. Receipt #{token_record.receipt_code}.{community_note}"
            ),
            created_at=now,
            dedup_key=f"return_receipt:{token_record.id}:{int(now.timestamp())}",
        )
        db.add(notification)

        return BookReturnDischargeResponse(
            success=True,
            message="Loan successfully discharged and returned to library inventory.",
            receipt_code=token_record.receipt_code or f"REC-{token_record.id}",
            loan_id=loan.id,
            book_title=book_title,
            copy_code=copy_code,
            patron_name=patron_name,
            returned_at=now,
            condition=condition,
            waitlist_advanced=waitlist_advanced,
        )


def get_pending_return_tokens_service(db: Session) -> List[BookReturnTokenItemResponse]:
    """Returns active in-flight return passes awaiting circulation desk check-in."""
    now = datetime.utcnow()
    tokens = db.execute(
        select(BookReturnToken)
        .where(
            BookReturnToken.is_used == False,
            BookReturnToken.expires_at > now,
        )
        .order_by(BookReturnToken.created_at.desc())
    ).scalars().all()

    items = []
    for t in tokens:
        if t.loan and t.loan.returned_at is None:
            loan = t.loan
            copy = loan.copy
            book = copy.book if copy else None
            items.append(
                BookReturnTokenItemResponse(
                    id=t.id,
                    loan_id=t.loan_id,
                    patron_id=t.user_id,
                    patron_name=t.user.full_name if t.user else f"Patron #{t.user_id}",
                    book_title=book.title if book else "Monograph",
                    copy_code=copy.copy_code if copy else "COPY",
                    raw_code=t.raw_code,
                    created_at=t.created_at,
                    expires_at=t.expires_at,
                )
            )
    return items


def get_return_receipt_service(db: Session, user: User, loan_id: int) -> BookReturnReceiptResponse:
    """Returns official printable return clearance receipt for a discharged loan."""
    loan = db.execute(select(Loan).where(Loan.id == loan_id)).scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan record not found.")

    if user.role != "librarian" and loan.student_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    if loan.returned_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loan is still active and has not been returned.")

    token_rec = db.execute(
        select(BookReturnToken).where(
            BookReturnToken.loan_id == loan.id,
            BookReturnToken.is_used == True,
        ).order_by(BookReturnToken.used_at.desc())
    ).scalars().first()

    receipt_code = token_rec.receipt_code if (token_rec and token_rec.receipt_code) else f"REC-{loan.id:06d}"
    discharged_by_name = token_rec.discharged_by.full_name if (token_rec and token_rec.discharged_by) else "Circulation Desk Staff"
    condition = token_rec.condition if token_rec else "good"
    condition_notes = token_rec.condition_notes if token_rec else None

    copy = loan.copy
    book = copy.book if copy else None

    return BookReturnReceiptResponse(
        receipt_code=receipt_code,
        institution_name="Athenaeum Academic Library",
        loan_id=loan.id,
        patron_id=loan.student_id,
        patron_name=loan.student.full_name if loan.student else "Patron",
        patron_email=loan.student.email if loan.student else None,
        book_title=book.title if book else "Monograph",
        book_author=book.author if book else None,
        copy_code=copy.copy_code if copy else "COPY",
        issued_at=loan.issued_at,
        due_date=loan.due_date,
        returned_at=loan.returned_at,
        discharged_by_name=discharged_by_name,
        condition=condition,
        condition_notes=condition_notes,
        status="CLEARED & DISCHARGED",
    )


def get_patron_clearance_status_service(db: Session, user: User) -> CirculationClearanceResponse:
    """
    Computes official Library Circulation Clearance / No Dues status for a patron.
    Non-punitive advisory: Does not restrict exams or academic milestones.
    """
    today = get_utc_today()
    active_loans = db.execute(
        select(Loan).where(
            Loan.student_id == user.id,
            Loan.returned_at.is_(None),
        ).order_by(Loan.due_date.asc())
    ).scalars().all()

    active_count = len(active_loans)
    overdue_count = sum(1 for l in active_loans if l.due_date < today)
    is_fully_cleared = (active_count == 0)

    active_items = []
    for l in active_loans:
        copy = l.copy
        book = copy.book if copy else None
        active_items.append({
            "loan_id": l.id,
            "book_title": book.title if book else "Monograph",
            "copy_code": copy.copy_code if copy else "COPY",
            "due_date": l.due_date.isoformat(),
            "is_overdue": l.due_date < today,
        })

    now = datetime.utcnow()
    if is_fully_cleared:
        headline = "Institutional Library Clearance Verified: All Monograph Accounts Clear"
        advisory = (
            "Congratulations! You have zero active loans and zero outstanding monograph liabilities. "
            "Your official Athenaeum Circulation Clearance Slip is ready for download or presentation."
        )
    else:
        headline = f"Academic Circulation Advisory: {active_count} Monograph(s) Currently on Loan"
        advisory = (
            f"You currently have {active_count} borrowed library monograph(s). This is a routine institutional "
            "advisory for your records and does not restrict your academic exams, grades, or campus privileges. "
            "Please return your books at the circulation desk when finished to maintain clean records."
        )

    return CirculationClearanceResponse(
        patron_id=user.id,
        patron_name=user.full_name,
        patron_role=user.role,
        active_loans_count=active_count,
        overdue_loans_count=overdue_count,
        is_fully_cleared=is_fully_cleared,
        status_headline=headline,
        advisory_message=advisory,
        can_export_certificate=is_fully_cleared,
        generated_at=now,
        active_items=active_items,
    )

