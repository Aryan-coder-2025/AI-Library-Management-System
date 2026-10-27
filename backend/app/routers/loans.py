"""
Loan circulation API router.
Provides endpoints for book issue, return, and loan queries.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user, require_librarian
from app.models import User
from app.schemas import LoanIssueRequest, LoanPaginationResponse, LoanResponse
from app.services import loans as loans_service

router = APIRouter(prefix="/api/loans", tags=["circulation"])


# ── Loan Issuance ─────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a physical book copy to an eligible student (librarian only)",
)
@router.post(
    "/issue",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a physical book copy to an eligible student (alias, librarian only)",
)
def issue_loan(
    issue_in: LoanIssueRequest,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Issues a book copy to a student.
    Enforces borrowing limits (< 3 active loans, no overdue loans), operational status checks,
    and calculates 14-day due date atomically.
    """
    return loans_service.issue_loan_service(
        db=db,
        issue_in=issue_in,
        librarian_id=current_user.id,
    )


# ── Loan Returns ──────────────────────────────────────────────────────────────

@router.post(
    "/{loan_id}/return",
    response_model=LoanResponse,
    status_code=status.HTTP_200_OK,
    summary="Record return of an active loan (librarian only)",
)
def return_loan(
    loan_id: int,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Records the return of an active loan, preserving all historical loan metadata intact.
    Rejects duplicate return attempts with 409 Conflict.
    """
    return loans_service.return_loan_service(db=db, loan_id=loan_id)


# ── Student Loans Query ───────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=LoanPaginationResponse,
    summary="List authenticated user's own loans",
)
@router.get(
    "/my-loans",
    response_model=LoanPaginationResponse,
    summary="List authenticated user's own loans (alias)",
)
def get_my_loans(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter: 'active', 'returned', or 'overdue'"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns the authenticated student's own loan history (both active and returned loans).
    Students can never view records belonging to other users.
    """
    return loans_service.get_student_loans_service(
        db=db,
        student_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status_filter,
    )


# ── Librarian Loans Listing ───────────────────────────────────────────────────

@router.get(
    "",
    response_model=LoanPaginationResponse,
    summary="List loans across all students with filters (librarian only)",
)
def list_all_loans(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    student_id: Optional[int] = Query(None, description="Filter by student user ID"),
    copy_id: Optional[int] = Query(None, description="Filter by physical copy ID"),
    book_id: Optional[int] = Query(None, description="Filter by catalogue book ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter: 'active', 'returned', or 'overdue'"),
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """
    Lists loan circulation records across students with pagination and multi-field filters.
    Librarian only.
    """
    return loans_service.list_all_loans_service(
        db=db,
        page=page,
        page_size=page_size,
        student_id=student_id,
        copy_id=copy_id,
        book_id=book_id,
        status=status_filter,
    )


# ── Individual Loan Detail ────────────────────────────────────────────────────

@router.get(
    "/{loan_id}",
    response_model=LoanResponse,
    summary="Retrieve an individual loan record by ID",
)
def get_loan_detail(
    loan_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full details of a single loan.
    Students may only view their own loans; librarians may view any loan.
    """
    return loans_service.get_loan_detail_service(
        db=db,
        loan_id=loan_id,
        current_user=current_user,
    )
