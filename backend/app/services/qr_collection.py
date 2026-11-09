"""
QR Book Collection Service (CIRC-03).
Generates secure, unpredictable single-use collection passes for patrons with ready holds,
and allows circulation staff to scan/verify tokens to authorize instant copy collection.
"""
from datetime import datetime, timedelta
import hashlib
import logging
import secrets
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import atomic_write
from app.models import BookCollectionToken, BookHold, Loan, User
from app.schemas import BookCollectionPassResponse, BookCollectionVerifyResponse
from app.services.loans import issue_loan_service
from app.schemas import LoanIssueRequest

logger = logging.getLogger("athenaeum.circulation.qr")

TOKEN_EXPIRE_MINUTES = 120  # 2-hour collection window


def hash_collection_token(token: str) -> str:
    """Computes deterministic SHA-256 hash of collection token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_book_collection_pass(db: Session, user: User, hold_id: int) -> BookCollectionPassResponse:
    """
    Generates a secure, time-limited collection token for a patron's ready hold.
    Prevents duplicate active tokens and guarantees token hash storage.
    """
    with atomic_write(db):
        hold = db.execute(
            select(BookHold).where(
                BookHold.id == hold_id,
                BookHold.user_id == user.id,
            )
        ).scalar_one_or_none()

        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book hold not found.")

        if hold.status != "ready_for_pickup":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate collection pass: hold status is '{hold.status}', expected 'ready_for_pickup'.",
            )

        if not hold.copy_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No physical copy has been allocated to this hold yet.",
            )

        # Invalidate previous unused collection tokens for this hold
        now = datetime.utcnow()
        active_tokens = db.execute(
            select(BookCollectionToken).where(
                BookCollectionToken.hold_id == hold.id,
                BookCollectionToken.is_used == False,
            )
        ).scalars().all()
        for t in active_tokens:
            t.is_used = True
            t.used_at = now

        # Generate clean, memorable unique numeric token code (6 digits, e.g. ATN-COLLECT-749201)
        while True:
            token_num = secrets.randbelow(900000) + 100000
            raw_token = f"ATN-COLLECT-{token_num}"
            token_hash = hash_collection_token(raw_token)
            existing_tok = db.execute(
                select(BookCollectionToken).where(BookCollectionToken.token_hash == token_hash)
            ).scalar_one_or_none()
            if not existing_tok:
                break

        # Token valid until hold pickup expires, or at least 48 hours
        if hold.pickup_expires_at:
            pickup_exp = hold.pickup_expires_at.replace(tzinfo=None) if hold.pickup_expires_at.tzinfo else hold.pickup_expires_at
            expires_at = pickup_exp if pickup_exp > now else (now + timedelta(hours=48))
        else:
            expires_at = now + timedelta(hours=48)

        token_record = BookCollectionToken(
            hold_id=hold.id,
            user_id=user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            is_used=False,
        )
        db.add(token_record)
        db.flush()

        copy = hold.copy
        book = hold.book

        return BookCollectionPassResponse(
            hold_id=hold.id,
            copy_id=hold.copy_id,
            copy_code=copy.copy_code if copy else "COPY",
            book_id=hold.book_id,
            book_title=book.title if book else "Monograph",
            patron_id=user.id,
            patron_name=user.full_name,
            token=raw_token,
            qr_payload=f"ATHENAEUM-COLLECT:{raw_token}",
            expires_at=expires_at,
        )


def verify_and_fulfill_qr_collection(
    db: Session,
    librarian: User,
    raw_token: str,
) -> BookCollectionVerifyResponse:
    """
    Circulation desk verification of patron's QR collection token.
    Atomically validates token, issues the loan, fulfills the hold, and consumes the token.
    Supports scanning the full QR payload, entering the raw token, or typing the 6-digit token number.
    """
    if librarian.role != "librarian":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only librarians can verify book collection tokens at the circulation desk.",
        )

    clean_token = raw_token.strip()
    if clean_token.startswith("ATHENAEUM-COLLECT:"):
        clean_token = clean_token.replace("ATHENAEUM-COLLECT:", "", 1).strip()

    # Generate candidate variations (full token, short code, TKN- prefix)
    candidates = [clean_token]
    upper_tok = clean_token.upper()
    if upper_tok not in candidates:
        candidates.append(upper_tok)
    if upper_tok.startswith("TKN-"):
        short_num = upper_tok.replace("TKN-", "", 1).strip()
        candidates.append(f"ATN-COLLECT-{short_num}")
        candidates.append(short_num)
    elif upper_tok.startswith("ATN-COLLECT-"):
        short_num = upper_tok.replace("ATN-COLLECT-", "", 1).strip()
        candidates.append(short_num)
        candidates.append(f"TKN-{short_num}")
    elif upper_tok.isdigit():
        candidates.append(f"ATN-COLLECT-{upper_tok}")
        candidates.append(f"TKN-{upper_tok}")

    with atomic_write(db):
        token_record = None
        for cand in candidates:
            cand_hash = hash_collection_token(cand)
            token_record = db.execute(
                select(BookCollectionToken).where(BookCollectionToken.token_hash == cand_hash)
            ).scalar_one_or_none()
            if token_record:
                break

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid collection pass token '{clean_token}'. Token not recognized or not found.",
            )

        if token_record.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This collection pass has already been consumed.",
            )

        now = datetime.utcnow()
        if token_record.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This collection pass has expired. Please ask the patron to generate a new pass.",
            )

        hold = token_record.hold
        if not hold or hold.status != "ready_for_pickup":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hold is no longer ready for pickup (current status: '{hold.status if hold else 'None'}').",
            )

        copy_id = hold.copy_id
        student_id = token_record.user_id

        # Issue the loan via loan service
        issue_req = LoanIssueRequest(student_id=student_id, copy_id=copy_id)
        loan_resp = issue_loan_service(db, issue_req, librarian_id=librarian.id)

        # Mark token consumed
        token_record.is_used = True
        token_record.used_at = now
        db.add(token_record)

        return BookCollectionVerifyResponse(
            success=True,
            message="Collection verified and loan successfully issued.",
            loan_id=loan_resp.id,
            book_title=loan_resp.book_title,
            copy_code=loan_resp.copy_code,
            patron_name=token_record.user.full_name if token_record.user else "Patron",
            due_date=loan_resp.due_date,
        )

