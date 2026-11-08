"""
Course Management, Reading Lists & Course Reserves Service (PORT-03, INTEL-06, CIRC-06).
Provides academic planning, syllabus resource management, and short-term reserve enforcement.
"""
from datetime import datetime
import logging
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import atomic_write
from app.models import Book, BookCopy, Course, CourseReadingListItem, CourseReserve, Loan, User
from app.schemas import (
    CourseCreateRequest,
    CourseListResponse,
    CourseReserveCreateRequest,
    CourseReserveResponse,
    CourseResponse,
    ReadingListItemCreateRequest,
    ReadingListItemResponse,
)

logger = logging.getLogger("athenaeum.courses")


def serialize_course(course: Course, db: Session) -> CourseResponse:
    """Serializes a Course model with dynamic counts."""
    rl_count = db.execute(
        select(func.count(CourseReadingListItem.id)).where(CourseReadingListItem.course_id == course.id)
    ).scalar() or 0

    res_count = db.execute(
        select(func.count(CourseReserve.id)).where(
            CourseReserve.course_id == course.id,
            CourseReserve.is_active == True,
        )
    ).scalar() or 0

    instructor_name = course.instructor.full_name if course.instructor else "Unknown Instructor"

    return CourseResponse(
        id=course.id,
        code=course.code,
        title=course.title,
        department=course.department,
        term=course.term,
        instructor_id=course.instructor_id,
        instructor_name=instructor_name,
        description=course.description,
        is_active=course.is_active,
        created_at=course.created_at,
        reading_list_count=rl_count,
        reserves_count=res_count,
    )


def create_course_service(db: Session, user: User, req: CourseCreateRequest) -> CourseResponse:
    """Creates a new academic course. Restricted to teachers and librarians."""
    if user.role not in ("teacher", "librarian"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and librarians can create academic courses.",
        )

    clean_code = req.code.strip().upper()
    with atomic_write(db):
        existing = db.execute(select(Course).where(func.upper(Course.code) == clean_code)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Course with code '{clean_code}' already exists.",
            )

        course = Course(
            code=clean_code,
            title=req.title.strip(),
            department=req.department.strip(),
            term=req.term.strip(),
            instructor_id=user.id,
            description=req.description.strip() if req.description else None,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(course)
        db.flush()
        db.refresh(course)
        return serialize_course(course, db)


def list_courses_service(
    db: Session,
    instructor_id: Optional[int] = None,
    department: Optional[str] = None,
    term: Optional[str] = None,
) -> CourseListResponse:
    """Lists academic courses with optional filtering."""
    query = select(Course).where(Course.is_active == True)
    if instructor_id:
        query = query.where(Course.instructor_id == instructor_id)
    if department:
        query = query.where(func.lower(Course.department) == department.strip().lower())
    if term:
        query = query.where(func.lower(Course.term) == term.strip().lower())

    courses = db.execute(query.order_by(Course.code.asc())).scalars().all()
    items = [serialize_course(c, db) for c in courses]
    return CourseListResponse(courses=items, total=len(items))


def get_course_service(db: Session, course_id: int) -> CourseResponse:
    """Retrieves single course details."""
    course = db.execute(select(Course).where(Course.id == course_id)).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    return serialize_course(course, db)


def add_reading_list_item_service(
    db: Session,
    user: User,
    course_id: int,
    req: ReadingListItemCreateRequest,
) -> ReadingListItemResponse:
    """Adds a monograph to a course's syllabus reading list."""
    with atomic_write(db):
        course = db.execute(select(Course).where(Course.id == course_id)).scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

        # Teacher authorization check
        if user.role == "teacher" and course.instructor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage reading lists for courses you instruct.",
            )
        elif user.role not in ("teacher", "librarian"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only instructors and librarians can modify course reading lists.",
            )

        book = db.execute(select(Book).where(Book.id == req.book_id, Book.is_archived == False)).scalar_one_or_none()
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book monograph not found or archived.")

        # Duplicate check
        existing = db.execute(
            select(CourseReadingListItem).where(
                CourseReadingListItem.course_id == course_id,
                CourseReadingListItem.book_id == req.book_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This monograph is already in the course reading list.",
            )

        item = CourseReadingListItem(
            course_id=course_id,
            book_id=req.book_id,
            added_by_id=user.id,
            requirement_type=req.requirement_type,
            notes=req.notes.strip() if req.notes else None,
            created_at=datetime.utcnow(),
        )
        db.add(item)
        db.flush()
        db.refresh(item)

        # Availability calculation
        loaned_copy_ids = select(Loan.copy_id).where(Loan.returned_at.is_(None))
        avail_count = db.execute(
            select(func.count(BookCopy.id)).where(
                BookCopy.book_id == req.book_id,
                BookCopy.operational_status == "available",
                BookCopy.id.not_in(loaned_copy_ids),
            )
        ).scalar() or 0

        total_copies = db.execute(
            select(func.count(BookCopy.id)).where(BookCopy.book_id == req.book_id)
        ).scalar() or 0

        return ReadingListItemResponse(
            id=item.id,
            course_id=item.course_id,
            book_id=item.book_id,
            book_title=book.title,
            book_author=book.author,
            book_isbn=book.isbn,
            added_by_id=item.added_by_id,
            requirement_type=item.requirement_type,
            notes=item.notes,
            created_at=item.created_at,
            available_copies_count=avail_count,
            total_copies_count=total_copies,
        )


def remove_reading_list_item_service(db: Session, user: User, course_id: int, item_id: int) -> None:
    """Removes a monograph from a course reading list."""
    with atomic_write(db):
        course = db.execute(select(Course).where(Course.id == course_id)).scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

        if user.role == "teacher" and course.instructor_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to modify this course.")
        elif user.role not in ("teacher", "librarian"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

        item = db.execute(
            select(CourseReadingListItem).where(
                CourseReadingListItem.id == item_id,
                CourseReadingListItem.course_id == course_id,
            )
        ).scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading list entry not found.")

        db.delete(item)


def get_course_reading_list_service(db: Session, course_id: int) -> List[ReadingListItemResponse]:
    """Retrieves all reading list entries for a course with live copy inventory availability."""
    course = db.execute(select(Course).where(Course.id == course_id)).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    items = db.execute(
        select(CourseReadingListItem)
        .where(CourseReadingListItem.course_id == course_id)
        .order_by(CourseReadingListItem.created_at.asc())
    ).scalars().all()

    loaned_copy_ids = select(Loan.copy_id).where(Loan.returned_at.is_(None))

    results = []
    for item in items:
        avail_count = db.execute(
            select(func.count(BookCopy.id)).where(
                BookCopy.book_id == item.book_id,
                BookCopy.operational_status == "available",
                BookCopy.id.not_in(loaned_copy_ids),
            )
        ).scalar() or 0

        total_copies = db.execute(
            select(func.count(BookCopy.id)).where(BookCopy.book_id == item.book_id)
        ).scalar() or 0

        book = item.book
        results.append(
            ReadingListItemResponse(
                id=item.id,
                course_id=item.course_id,
                book_id=item.book_id,
                book_title=book.title if book else "Unknown Title",
                book_author=book.author if book else None,
                book_isbn=book.isbn if book else None,
                added_by_id=item.added_by_id,
                requirement_type=item.requirement_type,
                notes=item.notes,
                created_at=item.created_at,
                available_copies_count=avail_count,
                total_copies_count=total_copies,
            )
        )
    return results


# ── Course Reserves (CIRC-06) ────────────────────────────────────────────────

def add_course_reserve_service(
    db: Session,
    user: User,
    course_id: int,
    req: CourseReserveCreateRequest,
) -> CourseReserveResponse:
    """
    Places a physical book copy on Course Reserve (2-hour or 24-hour loan limit).
    Guarantees copy is not currently on loan or allocated to an active hold.
    """
    if user.role not in ("teacher", "librarian"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and librarians can designate course reserves.",
        )

    with atomic_write(db):
        course = db.execute(select(Course).where(Course.id == course_id)).scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

        copy = db.execute(select(BookCopy).where(BookCopy.id == req.copy_id)).scalar_one_or_none()
        if not copy:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book physical copy not found.")

        if copy.operational_status != "available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Copy cannot be reserved because operational status is '{copy.operational_status}'.",
            )

        # Check existing active reserve
        existing_res = db.execute(
            select(CourseReserve).where(
                CourseReserve.copy_id == req.copy_id,
                CourseReserve.is_active == True,
            )
        ).scalar_one_or_none()
        if existing_res:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This copy is already designated as an active course reserve.",
            )

        reserve = CourseReserve(
            course_id=course_id,
            copy_id=req.copy_id,
            reserve_type=req.reserve_type,
            is_active=True,
            notes=req.notes.strip() if req.notes else None,
            created_at=datetime.utcnow(),
        )
        db.add(reserve)
        db.flush()
        db.refresh(reserve)

        book = copy.book
        return CourseReserveResponse(
            id=reserve.id,
            course_id=course.id,
            course_code=course.code,
            copy_id=copy.id,
            copy_code=copy.copy_code,
            book_id=copy.book_id,
            book_title=book.title if book else "Unknown",
            reserve_type=reserve.reserve_type,
            is_active=reserve.is_active,
            notes=reserve.notes,
            created_at=reserve.created_at,
        )


def remove_course_reserve_service(db: Session, user: User, reserve_id: int) -> None:
    """Removes a physical copy from course reserve."""
    if user.role not in ("teacher", "librarian"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    with atomic_write(db):
        reserve = db.execute(select(CourseReserve).where(CourseReserve.id == reserve_id)).scalar_one_or_none()
        if not reserve:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course reserve not found.")

        db.delete(reserve)


def list_course_reserves_service(db: Session, course_id: Optional[int] = None) -> List[CourseReserveResponse]:
    """Lists course reserve materials."""
    query = select(CourseReserve).where(CourseReserve.is_active == True)
    if course_id:
        query = query.where(CourseReserve.course_id == course_id)

    reserves = db.execute(query.order_by(CourseReserve.created_at.desc())).scalars().all()
    out = []
    for r in reserves:
        book = r.copy.book if r.copy else None
        out.append(
            CourseReserveResponse(
                id=r.id,
                course_id=r.course_id,
                course_code=r.course.code if r.course else "COURSE",
                copy_id=r.copy_id,
                copy_code=r.copy.copy_code if r.copy else "COPY",
                book_id=r.copy.book_id if r.copy else 0,
                book_title=book.title if book else "Unknown",
                reserve_type=r.reserve_type,
                is_active=r.is_active,
                notes=r.notes,
                created_at=r.created_at,
            )
        )
    return out

