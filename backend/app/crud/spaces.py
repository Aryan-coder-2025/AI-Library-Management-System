"""
Study Space CRUD operations.
Handles database queries and persistence for study zones, seats, rooms, and reservations.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Reservation, StudyRoom, StudySeat, StudyZone, User


def get_study_zones(db: Session, active_only: bool = True) -> List[StudyZone]:
    """Retrieves all study zones, optionally filtering to active only."""
    stmt = select(StudyZone)
    if active_only:
        stmt = stmt.where(StudyZone.is_active.is_(True))
    stmt = stmt.order_by(StudyZone.floor.asc(), StudyZone.name.asc())
    return list(db.execute(stmt).scalars().all())


def get_study_zone_by_id(db: Session, zone_id: int) -> Optional[StudyZone]:
    """Retrieves a single study zone by its ID."""
    stmt = select(StudyZone).where(StudyZone.id == zone_id)
    return db.execute(stmt).scalar_one_or_none()


def get_study_seat_by_id(db: Session, seat_id: int, populate_existing: bool = False) -> Optional[StudySeat]:
    """Retrieves a single study seat by ID."""
    stmt = select(StudySeat).options(joinedload(StudySeat.zone)).where(StudySeat.id == seat_id)
    if populate_existing:
        stmt = stmt.execution_options(populate_existing=True)
    return db.execute(stmt).scalar_one_or_none()


def get_study_room_by_id(db: Session, room_id: int, populate_existing: bool = False) -> Optional[StudyRoom]:
    """Retrieves a single study room by ID."""
    stmt = select(StudyRoom).where(StudyRoom.id == room_id)
    if populate_existing:
        stmt = stmt.execution_options(populate_existing=True)
    return db.execute(stmt).scalar_one_or_none()


def get_active_user_reservation_count(db: Session, user_id: int) -> int:
    """Returns the count of active reservations currently held by the specified user."""
    stmt = (
        select(func.count(Reservation.id))
        .where(Reservation.user_id == user_id, Reservation.status == "active")
    )
    return db.execute(stmt).scalar() or 0


def has_user_overlapping_active_reservation(
    db: Session,
    user_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_reservation_id: Optional[int] = None,
) -> bool:
    """Checks whether the user already holds an active reservation overlapping [start_time, end_time)."""
    stmt = select(func.count(Reservation.id)).where(
        Reservation.user_id == user_id,
        Reservation.status == "active",
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    if exclude_reservation_id is not None:
        stmt = stmt.where(Reservation.id != exclude_reservation_id)
    count = db.execute(stmt).scalar() or 0
    return count > 0


def has_seat_overlapping_active_reservation(
    db: Session,
    seat_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_reservation_id: Optional[int] = None,
) -> bool:
    """Checks whether the seat is already booked with an active reservation overlapping [start_time, end_time)."""
    stmt = select(func.count(Reservation.id)).where(
        Reservation.seat_id == seat_id,
        Reservation.status == "active",
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    if exclude_reservation_id is not None:
        stmt = stmt.where(Reservation.id != exclude_reservation_id)
    count = db.execute(stmt).scalar() or 0
    return count > 0


def has_room_overlapping_active_reservation(
    db: Session,
    room_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_reservation_id: Optional[int] = None,
) -> bool:
    """Checks whether the room is already booked with an active reservation overlapping [start_time, end_time)."""
    stmt = select(func.count(Reservation.id)).where(
        Reservation.room_id == room_id,
        Reservation.status == "active",
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    if exclude_reservation_id is not None:
        stmt = stmt.where(Reservation.id != exclude_reservation_id)
    count = db.execute(stmt).scalar() or 0
    return count > 0


def get_reservation_by_id(db: Session, reservation_id: int) -> Optional[Reservation]:
    """Retrieves a single reservation by ID with its user, seat, and room eagerly loaded."""
    stmt = (
        select(Reservation)
        .options(
            joinedload(Reservation.user),
            joinedload(Reservation.seat).joinedload(StudySeat.zone),
            joinedload(Reservation.room),
        )
        .where(Reservation.id == reservation_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_user_reservations(
    db: Session,
    user_id: int,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Reservation], int]:
    """Retrieves paginated reservations for a specific user."""
    base_filter = [Reservation.user_id == user_id]
    if status_filter:
        base_filter.append(Reservation.status == status_filter)

    count_stmt = select(func.count(Reservation.id)).where(*base_filter)
    total = db.execute(count_stmt).scalar() or 0

    offset = (page - 1) * page_size
    query_stmt = (
        select(Reservation)
        .options(
            joinedload(Reservation.seat),
            joinedload(Reservation.room),
        )
        .where(*base_filter)
        .order_by(Reservation.start_time.desc(), Reservation.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(db.execute(query_stmt).scalars().all())
    return items, total


def get_all_reservations(
    db: Session,
    user_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Reservation], int]:
    """Retrieves paginated reservations across all users with administrative filters."""
    filters = []
    if user_id is not None:
        filters.append(Reservation.user_id == user_id)
    if status_filter:
        filters.append(Reservation.status == status_filter)
    if resource_type:
        filters.append(Reservation.resource_type == resource_type)
    if start_date is not None:
        filters.append(Reservation.start_time >= start_date)
    if end_date is not None:
        filters.append(Reservation.end_time <= end_date)

    count_stmt = select(func.count(Reservation.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = db.execute(count_stmt).scalar() or 0

    offset = (page - 1) * page_size
    query_stmt = (
        select(Reservation)
        .options(
            joinedload(Reservation.user),
            joinedload(Reservation.seat),
            joinedload(Reservation.room),
        )
    )
    if filters:
        query_stmt = query_stmt.where(*filters)

    query_stmt = (
        query_stmt.order_by(Reservation.start_time.desc(), Reservation.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(db.execute(query_stmt).scalars().all())
    return items, total


def query_available_seats(
    db: Session,
    start_time: datetime,
    end_time: datetime,
    zone_id: Optional[int] = None,
    has_power: Optional[bool] = None,
    has_monitor: Optional[bool] = None,
    is_accessible: Optional[bool] = None,
) -> List[StudySeat]:
    """
    Returns active study seats that do not have an active reservation during [start_time, end_time).
    Does NOT leak private user reservation details.
    """
    conflict_subq = (
        select(Reservation.seat_id)
        .where(
            Reservation.resource_type == "seat",
            Reservation.status == "active",
            Reservation.start_time < end_time,
            Reservation.end_time > start_time,
        )
        .scalar_subquery()
    )

    filters = [
        StudySeat.is_active.is_(True),
        ~StudySeat.id.in_(conflict_subq),
    ]
    if zone_id is not None:
        filters.append(StudySeat.zone_id == zone_id)
    if has_power is not None:
        filters.append(StudySeat.has_power_outlet == has_power)
    if has_monitor is not None:
        filters.append(StudySeat.has_monitor == has_monitor)
    if is_accessible is not None:
        filters.append(StudySeat.is_accessible == is_accessible)

    stmt = select(StudySeat).where(*filters).order_by(StudySeat.seat_code.asc())
    return list(db.execute(stmt).scalars().all())


def query_available_rooms(
    db: Session,
    start_time: datetime,
    end_time: datetime,
    min_capacity: Optional[int] = None,
) -> List[StudyRoom]:
    """
    Returns active study rooms that do not have an active reservation during [start_time, end_time).
    Does NOT leak private user reservation details.
    """
    conflict_subq = (
        select(Reservation.room_id)
        .where(
            Reservation.resource_type == "room",
            Reservation.status == "active",
            Reservation.start_time < end_time,
            Reservation.end_time > start_time,
        )
        .scalar_subquery()
    )

    filters = [
        StudyRoom.is_active.is_(True),
        ~StudyRoom.id.in_(conflict_subq),
    ]
    if min_capacity is not None:
        filters.append(StudyRoom.capacity >= min_capacity)

    stmt = select(StudyRoom).where(*filters).order_by(StudyRoom.room_code.asc())
    return list(db.execute(stmt).scalars().all())


def atomic_check_in_reservation(
    db: Session,
    reservation_id: int,
    checked_in_at: datetime,
    actual_attendees: Optional[int] = None,
) -> int:
    """
    Atomically marks an active reservation as checked in.
    Uses a conditional update requiring status = 'active' and checked_in_at IS NULL.
    Returns the updated row count (1 if successful, 0 if already checked in or not active).
    """
    from sqlalchemy import update

    values = {"checked_in_at": checked_in_at}
    if actual_attendees is not None:
        values["actual_attendees"] = actual_attendees

    stmt = (
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.status == "active",
            Reservation.checked_in_at.is_(None),
        )
        .values(**values)
    )
    result = db.execute(stmt)
    return result.rowcount


def get_reservations_due_for_no_show(db: Session, cutoff_time: datetime) -> List[Reservation]:
    """
    Finds active reservations that have passed their check-in grace period cutoff
    without checking in (checked_in_at is NULL).
    """
    stmt = (
        select(Reservation)
        .where(
            Reservation.status == "active",
            Reservation.checked_in_at.is_(None),
            Reservation.start_time <= cutoff_time,
        )
        .order_by(Reservation.start_time.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_reservations_due_for_completion(db: Session, now_time: datetime) -> List[Reservation]:
    """
    Finds active reservations that were checked in (checked_in_at is NOT NULL)
    and whose scheduled end_time has passed.
    """
    stmt = (
        select(Reservation)
        .where(
            Reservation.status == "active",
            Reservation.checked_in_at.is_not(None),
            Reservation.end_time <= now_time,
        )
        .order_by(Reservation.end_time.asc())
    )
    return list(db.execute(stmt).scalars().all())


def mark_reservation_no_show(db: Session, reservation_id: int) -> int:
    """
    Transitions an active, un-checked-in reservation to 'no_show'.
    Returns updated row count.
    """
    from sqlalchemy import update

    stmt = (
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.status == "active",
            Reservation.checked_in_at.is_(None),
        )
        .values(status="no_show")
    )
    result = db.execute(stmt)
    return result.rowcount


def mark_reservation_completed(db: Session, reservation_id: int) -> int:
    """
    Transitions an active, checked-in reservation to 'completed'.
    Returns updated row count.
    """
    from sqlalchemy import update

    stmt = (
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.status == "active",
            Reservation.checked_in_at.is_not(None),
        )
        .values(status="completed")
    )
    result = db.execute(stmt)
    return result.rowcount

