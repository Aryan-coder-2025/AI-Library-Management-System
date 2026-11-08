"""
FastAPI Router for Academic Courses, Syllabus Reading Lists & Course Reserves (PORT-03, INTEL-06, CIRC-06).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_user, require_librarian, require_teacher
from app.models import User
from app.schemas import (
    CourseCreateRequest,
    CourseListResponse,
    CourseReserveCreateRequest,
    CourseReserveResponse,
    CourseResponse,
    MessageResponse,
    ReadingListItemCreateRequest,
    ReadingListItemResponse,
)
from app.services.courses import (
    add_course_reserve_service,
    add_reading_list_item_service,
    create_course_service,
    get_course_reading_list_service,
    get_course_service,
    list_course_reserves_service,
    list_courses_service,
    remove_course_reserve_service,
    remove_reading_list_item_service,
)

router = APIRouter(prefix="/api/courses", tags=["Academic Courses & Reserves"])


@router.get("", response_model=CourseListResponse, summary="List academic courses")
def list_courses(
    instructor_id: Optional[int] = Query(None, description="Filter by instructor user ID"),
    department: Optional[str] = Query(None, description="Filter by department"),
    term: Optional[str] = Query(None, description="Filter by term"),
    db: Session = Depends(get_db),
):
    """Lists courses. Publicly discoverable by students, teachers, and librarians."""
    return list_courses_service(db, instructor_id=instructor_id, department=department, term=term)


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED, summary="Create course")
def create_course(
    req: CourseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Creates a course. Restricted to teachers and librarians."""
    return create_course_service(db, current_user, req)


@router.get("/reserves", response_model=List[CourseReserveResponse], summary="List course reserves")
def list_reserves(
    course_id: Optional[int] = Query(None, description="Filter reserves by course ID"),
    db: Session = Depends(get_db),
):
    """Lists active course reserves."""
    return list_course_reserves_service(db, course_id=course_id)


@router.get("/{course_id}", response_model=CourseResponse, summary="Get course details")
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
):
    """Retrieves course details."""
    return get_course_service(db, course_id)


@router.get("/{course_id}/reading-list", response_model=List[ReadingListItemResponse], summary="Get reading list")
def get_reading_list(
    course_id: int,
    db: Session = Depends(get_db),
):
    """Returns syllabus reading list for a course with live copy inventory availability."""
    return get_course_reading_list_service(db, course_id)


@router.post("/{course_id}/reading-list", response_model=ReadingListItemResponse, status_code=status.HTTP_201_CREATED, summary="Add to reading list")
def add_reading_list_item(
    course_id: int,
    req: ReadingListItemCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Adds a monograph to course reading list. Restricted to course instructor or librarian."""
    return add_reading_list_item_service(db, current_user, course_id, req)


@router.delete("/{course_id}/reading-list/{item_id}", response_model=MessageResponse, summary="Remove from reading list")
def remove_reading_list_item(
    course_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Removes a monograph from reading list. Restricted to course instructor or librarian."""
    remove_reading_list_item_service(db, current_user, course_id, item_id)
    return MessageResponse(message="Reading list item removed successfully.")


@router.post("/{course_id}/reserves", response_model=CourseReserveResponse, status_code=status.HTTP_201_CREATED, summary="Add course reserve copy")
def add_course_reserve(
    course_id: int,
    req: CourseReserveCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Places a physical copy on course reserve (2-hour or 24-hour). Restricted to teachers/librarians."""
    return add_course_reserve_service(db, current_user, course_id, req)


@router.delete("/reserves/{reserve_id}", response_model=MessageResponse, summary="Remove course reserve")
def remove_course_reserve(
    reserve_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Removes a physical copy from course reserve. Restricted to teachers/librarians."""
    remove_course_reserve_service(db, current_user, reserve_id)
    return MessageResponse(message="Course reserve removed successfully.")

