"""
Loan circulation service layer.
Coordinates loan issuance, returns, business policy enforcement, and atomic transactions.
"""
from datetime import date, datetime, timedelta
import math
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import loans as crud_loans
from app.database import atomic_write
from app.models import Loan, User
from app.schemas import LoanIssueRequest, LoanPaginationResponse, LoanResponse


def serialize_loan(loan: Loan, as_of_date: Optional[date] = None) -> LoanResponse:
    """Computes dynamic overdue/active status and serializes a loan record."""
    today = as_of_date or date.today()
    if loan.returned_at is not None:
        computed_status = "returned"
        is_overdue = False
    elif loan.due_date < today:
        computed_status = "overdue"
        is_overdue = True
    else:
        computed_status = "active"
        is_overdue = False

    book_id = 0
    book_title = ""
    book_author = None
    if loan.copy and loan.copy.book:
        book_id = loan.copy.book.id
        book_title = loan.copy.book.title
        book_author = loan.copy.book.author

    copy_code = loan.copy.copy_code if loan.copy else ""

    student_name = loan.student.full_name if loan.student else None
    student_email = loan.student.email if loan.student else None

    return LoanResponse(
        id=loan.id,
        student_id=loan.student_id,
        student_name=student_name,
        student_email=student_email,
        copy_id=loan.copy_id,
        copy_code=copy_code,
        book_id=book_id,
        book_title=book_title,
        book_author=book_author,
        issued_by_id=loan.issued_by_id,
        issued_at=loan.issued_at,
        due_date=loan.due_date,
        returned_at=loan.returned_at,
        status=computed_status,
        is_overdue=is_overdue,
    )


def issue_loan_service(
    db: Session,
    issue_in: LoanIssueRequest,
    librarian_id: int,
) -> LoanResponse:
    """
    Issues a physical book copy to an eligible student in an atomic write transaction.
    Enforces all Stage 4 eligibility and concurrency safeguards:
    - Student exists, is active, and possesses the 'student' role.
    - Book copy exists, is not archived, and is not retired.
    - Copy operational status is 'available'.
    - Copy has no active loan.
    - Student has fewer than 3 active loans.
    - Student has no overdue active loans.
    - 14 calendar days due date computed from server date.
    - Issued_by_id set from authenticated librarian.
    """
    with atomic_write(db):
        student = crud_loans.get_user_by_id(db, issue_in.student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found.",
            )
        if not student.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student account is inactive and cannot borrow books.",
            )
        if student.role != "student":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only accounts with the student role can borrow books.",
            )

        copy = crud_loans.get_copy_by_id(db, issue_in.copy_id)
        if not copy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book copy not found.",
            )
        if copy.book.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot borrow a copy belonging to an archived book.",
            )
        if copy.operational_status == "retired":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Book copy is retired and cannot be borrowed.",
            )
        if copy.operational_status != "available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Book copy is currently in '{copy.operational_status}' status and cannot be borrowed.",
            )

        if crud_loans.has_active_loan_for_copy(db, copy.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Book copy is currently on loan.",
            )

        active_count = crud_loans.get_student_active_loan_count(db, student.id)
        if active_count >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student has reached the maximum borrowing limit of 3 active loans.",
            )

        today = date.today()
        if crud_loans.student_has_overdue_loans(db, student.id, as_of_date=today):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student has overdue loans and cannot borrow new books until overdue items are returned.",
            )

        issued_at = datetime.utcnow()
        due_date = today + timedelta(days=14)

        try:
            loan = crud_loans.create_loan(
                db=db,
                student_id=student.id,
                copy_id=copy.id,
                issued_by_id=librarian_id,
                issued_at=issued_at,
                due_date=due_date,
            )
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Book copy is currently on loan.",
            )

        return serialize_loan(loan, as_of_date=today)


def return_loan_service(db: Session, loan_id: int) -> LoanResponse:
    """
    Records the return of an active book loan in an atomic write transaction.
    - Verifies the loan exists and has not already been returned.
    - Sets returned_at to current server time.
    - Preserves historical loan metadata intact.
    - Rejects duplicate return attempts with 409 Conflict.
    - Does not alter copy operational status (only available copies become available).
    """
    with atomic_write(db):
        loan = crud_loans.get_loan(db, loan_id)
        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan record not found.",
            )
        if loan.returned_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Loan has already been returned.",
            )

        returned_loan = crud_loans.return_loan(db, loan, returned_at=datetime.utcnow())
        return serialize_loan(returned_loan)


def get_student_loans_service(
    db: Session,
    student_id: int,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
) -> LoanPaginationResponse:
    """
    Retrieves loans for a specific student with pagination and status filtering.
    """
    today = date.today()
    loans, total_count = crud_loans.get_loans(
        db=db,
        page=page,
        page_size=page_size,
        student_id=student_id,
        status=status,
        as_of_date=today,
    )
    items: List[LoanResponse] = [serialize_loan(l, as_of_date=today) for l in loans]
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

    return LoanPaginationResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_loan_detail_service(
    db: Session,
    loan_id: int,
    current_user: User,
) -> LoanResponse:
    """
    Retrieves a single loan record.
    Enforces privacy: students can only access their own loan records; librarians can access any.
    """
    loan = crud_loans.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan record not found.",
        )

    if current_user.role != "librarian" and loan.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this loan record.",
        )

    return serialize_loan(loan)


def list_all_loans_service(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    student_id: Optional[int] = None,
    copy_id: Optional[int] = None,
    book_id: Optional[int] = None,
    status: Optional[str] = None,
) -> LoanPaginationResponse:
    """
    Librarian listing of loans across all students with pagination and multi-field filters.
    """
    today = date.today()
    loans, total_count = crud_loans.get_loans(
        db=db,
        page=page,
        page_size=page_size,
        student_id=student_id,
        copy_id=copy_id,
        book_id=book_id,
        status=status,
        as_of_date=today,
    )
    items: List[LoanResponse] = [serialize_loan(l, as_of_date=today) for l in loans]
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

    return LoanPaginationResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
