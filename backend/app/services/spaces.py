"""
Study space reservation service layer.
Coordinates study-space reservation lifecycle, business policy enforcement,
operating hours validation, attendee constraints, and atomic transactions.
"""
import logging
import secrets
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.crud import spaces as crud_spaces
from app.models import Reservation, User
from app.schemas import (
    ReservationCheckInRequest,
    ReservationCheckInWithTokenRequest,
    ReservationCreate,
    ReservationPaginationResponse,
    ReservationQRResponse,
    ReservationResponse,
    ReservationSweepReport,
    SpaceAvailabilityResponse,
    StudyRoomResponse,
    StudySeatResponse,
    StudyZoneResponse,
)
from app.utils.date import get_library_timezone, get_utc_now


def get_reservation_policy(role: Optional[str]) -> Optional[Dict[str, object]]:
    """
    Returns the booking quota, advance window, and concurrency policy for a given user role.
    Default-denies unknown, missing, or inactive roles.
    """
    if not role or role not in ("student", "teacher", "librarian", "admin"):
        return None

    settings = get_settings()
    if role == "student":
        return {
            "max_active": settings.STUDENT_MAX_ACTIVE_RESERVATIONS,
            "advance_days": settings.STUDENT_ADVANCE_BOOKING_DAYS,
            "allow_overlap": False,
            "role_name": "student",
        }
    if role == "teacher":
        return {
            "max_active": settings.TEACHER_MAX_ACTIVE_RESERVATIONS,
            "advance_days": settings.TEACHER_ADVANCE_BOOKING_DAYS,
            "allow_overlap": False,
            "role_name": "teacher",
        }
    # librarian or admin
    return {
        "max_active": None,
        "advance_days": settings.LIBRARIAN_ADVANCE_BOOKING_DAYS,
        "allow_overlap": True,
        "role_name": role,
    }


def normalize_utc_datetime(dt: datetime) -> datetime:
    """Ensures datetime is evaluated in UTC and represented as naive UTC for SQLite storage."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def classify_spaces_db_exception(err: Exception, action: str = "processing") -> HTTPException:
    """
    Classifies database exceptions from study space operations according to the Stage 10.2.2 architecture contract:
    - Known resource/user conflict or uniqueness triggers -> HTTP 409 Conflict
    - SQLite lock contention (SQLITE_BUSY / SQLITE_LOCKED) -> HTTP 503 Service Unavailable (Retry-After: 1)
    - Unexpected IntegrityError -> HTTP 500 Internal Server Error (sanitized, internal details logged)
    - Unexpected OperationalError / database error -> HTTP 500 Internal Server Error (sanitized, internal details logged)

    Guarantees:
    - Never leaks SQL statements, table/column names, trigger implementations, or driver details.
    - Inspects driver metadata (sqlite_errorcode, sqlite_errorname) when available.
    """
    orig = getattr(err, "orig", None)
    sqlite_code = getattr(orig, "sqlite_errorcode", None)
    sqlite_name = getattr(orig, "sqlite_errorname", None)
    primary_code = (sqlite_code & 0xFF) if isinstance(sqlite_code, int) else None
    err_msg = str(err)
    err_lower = err_msg.lower()

    # 1. SQLite busy / locked contention (primary codes 5 and 6, extended SQLITE_BUSY_* / SQLITE_LOCKED_*)
    if (
        primary_code in (5, 6)
        or (sqlite_name and (sqlite_name.startswith("SQLITE_BUSY") or sqlite_name.startswith("SQLITE_LOCKED")))
        or "database is locked" in err_lower
        or "database is busy" in err_lower
        or "busytimeout" in err_lower
    ):
        logger.warning("Database lock contention encountered while %s reservation: %s", action, err)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The reservation service is currently busy. Please retry your request shortly.",
            headers={"Retry-After": "1"},
        )

    # 2. Known reservation conflicts (triggers and uniqueness constraints on reservations)
    if (
        "reservation conflict" in err_lower
        or "trg_prevent_" in err_lower
        or "unique constraint failed: reservations" in err_lower
        or (
            sqlite_name == "SQLITE_CONSTRAINT"
            and "reservations" in err_lower
            and ("conflict" in err_lower or "unique" in err_lower or "trg_" in err_lower)
        )
    ):
        logger.info("Known reservation conflict caught while %s reservation: %s", action, err)
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reservation conflict: resource or user already has an active reservation during this time interval.",
        )

    # 3. Unexpected integrity failures (never leak SQL, tables, triggers or schema)
    if isinstance(err, IntegrityError):
        logger.error("Unexpected database integrity failure while %s reservation: %s", action, err, exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal database integrity error occurred while {action} the reservation.",
        )

    # 4. Unexpected operational failures (never leak driver details or SQL)
    logger.error("Unexpected database operational failure while %s reservation: %s", action, err, exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"An internal database operational error occurred while {action} the reservation.",
    )


def validate_reservation_times(
    start_time: datetime,
    end_time: datetime,
    resource_type: str,
    policy: Dict[str, object],
    now_utc: Optional[datetime] = None,
) -> None:
    """
    Validates interval constraints, advance booking window, duration limits,
    and library operating hours in the institutional timezone.
    Strictly requires start_time >= now_utc with zero past-start tolerance.
    """
    settings = get_settings()
    if now_utc is None:
        now_utc = normalize_utc_datetime(get_utc_now())
    else:
        now_utc = normalize_utc_datetime(now_utc)

    # 1. Start must be strictly before end
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation end time must be strictly after start time.",
        )

    # 2. Cannot book in the past (strict start_time >= now_utc)
    if start_time < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation start time cannot be in the past.",
        )

    # 3. Advance booking window
    advance_days = int(policy["advance_days"])
    if start_time > now_utc + timedelta(days=advance_days):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reservations can only be made up to {advance_days} days in advance for your role.",
        )

    # 4. Duration constraints
    duration_minutes = (end_time - start_time).total_seconds() / 60.0
    if duration_minutes < settings.MIN_RESERVATION_DURATION_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reservation duration must be at least {settings.MIN_RESERVATION_DURATION_MINUTES} minutes.",
        )

    if resource_type == "seat" and duration_minutes > settings.MAX_SEAT_RESERVATION_HOURS * 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Seat reservations cannot exceed {settings.MAX_SEAT_RESERVATION_HOURS} hours.",
        )

    if resource_type == "room" and duration_minutes > settings.MAX_ROOM_RESERVATION_HOURS * 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room reservations cannot exceed {settings.MAX_ROOM_RESERVATION_HOURS} hours.",
        )

    # 5. Operating hours in institutional timezone
    inst_tz = get_library_timezone(settings.LIBRARY_TIMEZONE)
    local_start = start_time.replace(tzinfo=timezone.utc).astimezone(inst_tz)
    local_end = end_time.replace(tzinfo=timezone.utc).astimezone(inst_tz)

    if local_start.date() != local_end.date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservations must start and end on the same calendar day.",
        )

    open_hour, open_min = map(int, settings.LIBRARY_OPEN_TIME.split(":"))
    close_hour, close_min = map(int, settings.LIBRARY_CLOSE_TIME.split(":"))
    open_t = time(open_hour, open_min)
    close_t = time(close_hour, close_min)

    if local_start.time() < open_t or local_end.time() > close_t:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reservations must be within library operating hours ({settings.LIBRARY_OPEN_TIME} to {settings.LIBRARY_CLOSE_TIME} {settings.LIBRARY_TIMEZONE}).",
        )


def create_reservation_service(
    db: Session,
    user: User,
    data: ReservationCreate,
    now_utc: Optional[datetime] = None,
) -> ReservationResponse:
    """
    Creates a new study space reservation within an active write transaction.
    Enforces role quotas, advance windows, attendee bounds, operating hours,
    and user/resource overlap serialization.
    """
    # 1. Role validation
    policy = get_reservation_policy(user.role)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User role '{user.role}' is not authorized to create study space reservations.",
        )

    # 2. Time normalization and validation
    start_time = normalize_utc_datetime(data.start_time)
    end_time = normalize_utc_datetime(data.end_time)
    validate_reservation_times(start_time, end_time, data.resource_type, policy, now_utc=now_utc)

    # 3. Active booking quota check
    max_active = policy["max_active"]
    if max_active is not None:
        active_count = crud_spaces.get_active_user_reservation_count(db, user.id)
        if active_count >= max_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User has reached the maximum allowed active reservations for their role ({max_active}).",
            )

    # 4. User-level overlap check (for students and teachers)
    if not policy["allow_overlap"]:
        if crud_spaces.has_user_overlapping_active_reservation(db, user.id, start_time, end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reservation conflict: user already has an active reservation during this time interval.",
            )

    # 5. Resource validation & attendee bounds
    if data.resource_type == "seat":
        seat = crud_spaces.get_study_seat_by_id(db, data.seat_id, populate_existing=True)
        if not seat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Study seat with ID {data.seat_id} not found.",
            )
        if not seat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Study seat '{seat.seat_code}' is currently unavailable.",
            )
        expected_attendees = 1
        if crud_spaces.has_seat_overlapping_active_reservation(db, seat.id, start_time, end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reservation conflict: seat is already reserved during this time interval.",
            )
        room_id = None
        seat_id = seat.id

    elif data.resource_type == "room":
        room = crud_spaces.get_study_room_by_id(db, data.room_id, populate_existing=True)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Study room with ID {data.room_id} not found.",
            )
        if not room.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Study room '{room.name}' is currently unavailable.",
            )
        attendees = data.expected_attendees if data.expected_attendees is not None else 1
        if attendees < 1 or attendees > room.capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Expected attendees ({attendees}) must be between 1 and room capacity ({room.capacity}).",
            )
        expected_attendees = attendees
        if crud_spaces.has_room_overlapping_active_reservation(db, room.id, start_time, end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reservation conflict: room is already reserved during this time interval.",
            )
        room_id = room.id
        seat_id = None
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid resource type '{data.resource_type}'.",
        )

    # 6. Database insertion
    reservation = Reservation(
        user_id=user.id,
        resource_type=data.resource_type,
        seat_id=seat_id,
        room_id=room_id,
        start_time=start_time,
        end_time=end_time,
        status="active",
        expected_attendees=expected_attendees,
    )
    db.add(reservation)
    try:
        db.flush()
    except (IntegrityError, OperationalError) as err:
        raise classify_spaces_db_exception(err, action="processing")

    return ReservationResponse.model_validate(reservation)


def cancel_reservation_service(
    db: Session,
    user: User,
    reservation_id: int,
) -> ReservationResponse:
    """
    Cancels an active reservation.
    Patrons may cancel their own active reservations before they end.
    Librarians/admins may cancel any active reservation.
    """
    reservation = crud_spaces.get_reservation_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    if user.role not in ("librarian", "admin") and reservation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to cancel this reservation.",
        )

    if reservation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only active reservations can be cancelled (current status: {reservation.status}).",
        )

    now_utc = normalize_utc_datetime(get_utc_now())
    if reservation.end_time <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Past reservations cannot be cancelled.",
        )

    reservation.status = "cancelled"
    try:
        db.flush()
    except (IntegrityError, OperationalError) as err:
        raise classify_spaces_db_exception(err, action="cancelling")

    return ReservationResponse.model_validate(reservation)


def get_reservation_service(
    db: Session,
    user: User,
    reservation_id: int,
) -> ReservationResponse:
    """
    Retrieves reservation details.
    Restricted to reservation owner or librarians/admins.
    """
    reservation = crud_spaces.get_reservation_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    if user.role not in ("librarian", "admin") and reservation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this reservation.",
        )

    return ReservationResponse.model_validate(reservation)


def get_my_reservations_service(
    db: Session,
    user: User,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> ReservationPaginationResponse:
    """Retrieves paginated reservations for the authenticated patron."""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    items, total = crud_spaces.get_user_reservations(
        db=db,
        user_id=user.id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return ReservationPaginationResponse(
        items=[ReservationResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_all_reservations_service(
    db: Session,
    user: User,
    user_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> ReservationPaginationResponse:
    """Retrieves paginated reservations across all patrons with administrative filters."""
    if user.role not in ("librarian", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to list all reservations.",
        )

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    if start_date:
        start_date = normalize_utc_datetime(start_date)
    if end_date:
        end_date = normalize_utc_datetime(end_date)

    items, total = crud_spaces.get_all_reservations(
        db=db,
        user_id=user_id,
        status_filter=status_filter,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return ReservationPaginationResponse(
        items=[ReservationResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def query_space_availability_service(
    db: Session,
    start_time: datetime,
    end_time: datetime,
    resource_type: Optional[str] = None,
    zone_id: Optional[int] = None,
    min_capacity: Optional[int] = None,
    has_power: Optional[bool] = None,
    has_monitor: Optional[bool] = None,
    is_accessible: Optional[bool] = None,
) -> SpaceAvailabilityResponse:
    """
    Queries real-time seat and room availability over an interval.
    Does NOT leak personal user data or private reservation details.
    """
    start_time = normalize_utc_datetime(start_time)
    end_time = normalize_utc_datetime(end_time)

    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be strictly after start_time.",
        )

    seats: List[StudySeatResponse] = []
    rooms: List[StudyRoomResponse] = []

    if resource_type in (None, "seat"):
        raw_seats = crud_spaces.query_available_seats(
            db=db,
            start_time=start_time,
            end_time=end_time,
            zone_id=zone_id,
            has_power=has_power,
            has_monitor=has_monitor,
            is_accessible=is_accessible,
        )
        seats = [StudySeatResponse.model_validate(s) for s in raw_seats]

    if resource_type in (None, "room"):
        raw_rooms = crud_spaces.query_available_rooms(
            db=db,
            start_time=start_time,
            end_time=end_time,
            min_capacity=min_capacity,
        )
        rooms = [StudyRoomResponse.model_validate(r) for r in raw_rooms]

    return SpaceAvailabilityResponse(
        start_time=start_time,
        end_time=end_time,
        seats=seats,
        rooms=rooms,
        total_available_seats=len(seats),
        total_available_rooms=len(rooms),
    )


def get_study_zones_service(db: Session) -> List[StudyZoneResponse]:
    """Retrieves all active study zones."""
    zones = crud_spaces.get_study_zones(db=db, active_only=True)
    return [StudyZoneResponse.model_validate(z) for z in zones]


# ── Stage 10.3: QR Check-In, Grace Periods & No-Show Lifecycle ────────────────


def get_spaces_qr_secret_key() -> str:
    """
    Retrieves the dedicated signing secret key for study space QR tokens.
    Fails safely with HTTP 500 if unconfigured or blank, preventing weakly signed tokens.
    """
    settings = get_settings()
    key = settings.SPACES_QR_SECRET_KEY
    if not key or not str(key).strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Study space QR signing secret (SPACES_QR_SECRET_KEY) is not configured.",
        )
    return str(key).strip()


def generate_qr_checkin_token(reservation: Reservation) -> str:
    """
    Generates a cryptographically signed QR check-in token (JWT) bound to a specific reservation
    using the dedicated SPACES_QR_SECRET_KEY.
    Valid until the grace period window closes (start_time + CHECKIN_GRACE_PERIOD_MINUTES).
    """
    settings = get_settings()
    qr_secret = get_spaces_qr_secret_key()
    now_utc = normalize_utc_datetime(get_utc_now())
    grace_expiry = reservation.start_time + timedelta(minutes=settings.CHECKIN_GRACE_PERIOD_MINUTES)
    exp_time = max(now_utc + timedelta(minutes=30), grace_expiry)

    payload: Dict[str, Any] = {
        "type": "study_space_qr_checkin",
        "sub": f"res:{reservation.id}",
        "reservation_id": reservation.id,
        "user_id": reservation.user_id,
        "resource_type": reservation.resource_type,
        "resource_id": reservation.seat_id if reservation.resource_type == "seat" else reservation.room_id,
        "start_time": reservation.start_time.isoformat(),
        "end_time": reservation.end_time.isoformat(),
        "jti": secrets.token_hex(12),
        "iat": int(now_utc.replace(tzinfo=timezone.utc).timestamp()),
        "exp": int(exp_time.replace(tzinfo=timezone.utc).timestamp()),
    }
    return jwt.encode(payload, qr_secret, algorithm=settings.JWT_ALGORITHM)


def verify_qr_checkin_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a signed QR check-in token against the dedicated SPACES_QR_SECRET_KEY.
    Raises HTTPException 400 on signature error, expired token, or invalid payload.
    """
    qr_secret = get_spaces_qr_secret_key()
    settings = get_settings()
    try:
        payload = jwt.decode(token, qr_secret, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as err:
        logger.warning("QR token validation failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired QR check-in token.",
        )

    if payload.get("type") != "study_space_qr_checkin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is not a valid study space check-in token.",
        )

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.startswith("res:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR token subject is invalid or malformed.",
        )

    try:
        int(sub.split("res:", 1)[1])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR token subject contains an invalid reservation identifier.",
        )

    if "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR token payload is missing required reservation bindings.",
        )

    return payload


def get_reservation_qr_token_service(
    db: Session,
    user: User,
    reservation_id: int,
) -> ReservationQRResponse:
    """
    Retrieves a signed QR check-in token and metadata for a reservation.
    Only the reservation owner or librarians/admins can obtain the QR token.
    """
    settings = get_settings()
    reservation = crud_spaces.get_reservation_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    if user.role not in ("librarian", "admin") and reservation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this reservation's QR pass.",
        )

    if reservation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"QR pass is only available for active reservations (current status: {reservation.status}).",
        )

    qr_token = generate_qr_checkin_token(reservation)
    window_start = reservation.start_time - timedelta(minutes=settings.CHECKIN_WINDOW_BEFORE_MINUTES)
    window_end = reservation.start_time + timedelta(minutes=settings.CHECKIN_GRACE_PERIOD_MINUTES)

    if reservation.resource_type == "seat" and reservation.seat:
        resource_name = f"Seat {reservation.seat.seat_code}"
    elif reservation.resource_type == "room" and reservation.room:
        resource_name = f"Room {reservation.room.name}"
    else:
        resource_name = f"{reservation.resource_type.capitalize()} #{reservation.seat_id or reservation.room_id}"

    return ReservationQRResponse(
        reservation_id=reservation.id,
        qr_token=qr_token,
        expires_at=window_end,
        start_time=reservation.start_time,
        end_time=reservation.end_time,
        resource_type=reservation.resource_type,
        resource_name=resource_name,
        checkin_window_start=window_start,
        checkin_window_end=window_end,
    )


def check_in_reservation_service(
    db: Session,
    user: User,
    reservation_id: int,
    qr_token: Optional[str] = None,
    actual_attendees: Optional[int] = None,
    now_utc: Optional[datetime] = None,
) -> ReservationResponse:
    """
    Executes a transactional, atomic check-in for an active reservation.
    Enforces check-in window, grace period bounds, attendee validation,
    and conditional update concurrency serialization.
    """
    settings = get_settings()
    if now_utc is None:
        now_utc = normalize_utc_datetime(get_utc_now())
    else:
        now_utc = normalize_utc_datetime(now_utc)

    # 1. Fetch reservation
    reservation = crud_spaces.get_reservation_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    # 2. Verify QR token if supplied
    if qr_token is not None:
        token_payload = verify_qr_checkin_token(qr_token)
        sub = str(token_payload.get("sub", ""))
        try:
            token_res_id = int(sub.split("res:", 1)[1])
        except (ValueError, IndexError):
            token_res_id = int(token_payload.get("reservation_id", -1))

        if token_res_id != reservation.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR token does not match the target reservation.",
            )
        if int(token_payload["user_id"]) != reservation.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR token was not issued for this user.",
            )
        if token_payload.get("resource_type") != reservation.resource_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR token resource type mismatch.",
            )

    # 3. Authorization check
    is_admin = user.role in ("librarian", "admin")
    if not is_admin and reservation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to check in to this reservation.",
        )

    # 4. Status validation
    if reservation.status != "active":
        if reservation.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cancelled reservations cannot be checked in.",
            )
        if reservation.status == "no_show":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reservation was marked as no-show and cannot be checked in.",
            )
        if reservation.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completed reservations cannot be checked in.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only active reservations can be checked in (current status: {reservation.status}).",
        )

    if reservation.checked_in_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation is already checked in.",
        )

    # 5. Timing & window validation
    window_open = reservation.start_time - timedelta(minutes=settings.CHECKIN_WINDOW_BEFORE_MINUTES)
    grace_deadline = reservation.start_time + timedelta(minutes=settings.CHECKIN_GRACE_PERIOD_MINUTES)

    if now_utc < window_open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Check-in window opens {settings.CHECKIN_WINDOW_BEFORE_MINUTES} minutes before scheduled start time.",
        )

    if now_utc >= reservation.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation has already passed its scheduled end time.",
        )

    # Non-admin patrons are rejected after the grace period deadline
    if not is_admin and now_utc > grace_deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Check-in window closed {settings.CHECKIN_GRACE_PERIOD_MINUTES} minutes after scheduled start time. Reservation is subject to no-show release.",
        )

    # 6. Attendee validation
    if reservation.resource_type == "seat":
        validated_attendees = 1
    elif reservation.resource_type == "room":
        room = reservation.room or crud_spaces.get_study_room_by_id(db, reservation.room_id)
        capacity = room.capacity if room else 10
        if actual_attendees is not None:
            if actual_attendees < 1 or actual_attendees > capacity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Actual attendees ({actual_attendees}) must be between 1 and room capacity ({capacity}).",
                )
            validated_attendees = actual_attendees
        else:
            validated_attendees = reservation.expected_attendees
    else:
        validated_attendees = 1

    # 7. Atomic conditional update: enforces checked_in_at IS NULL so concurrent check-ins cannot succeed twice
    rows_updated = crud_spaces.atomic_check_in_reservation(
        db=db,
        reservation_id=reservation.id,
        checked_in_at=now_utc,
        actual_attendees=validated_attendees,
    )

    if rows_updated == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reservation is already checked in or no longer active.",
        )

    try:
        db.flush()
    except (IntegrityError, OperationalError) as err:
        raise classify_spaces_db_exception(err, action="checking in")

    # Refresh and return
    db.refresh(reservation)
    return ReservationResponse.model_validate(reservation)


def check_in_by_qr_token_service(
    db: Session,
    user: User,
    qr_token: str,
    actual_attendees: Optional[int] = None,
    now_utc: Optional[datetime] = None,
) -> ReservationResponse:
    """
    Scans a QR token and checks in the corresponding reservation.
    """
    token_payload = verify_qr_checkin_token(qr_token)
    sub = str(token_payload.get("sub", ""))
    try:
        reservation_id = int(sub.split("res:", 1)[1])
    except (ValueError, IndexError):
        reservation_id = int(token_payload.get("reservation_id", -1))
    return check_in_reservation_service(
        db=db,
        user=user,
        reservation_id=reservation_id,
        qr_token=qr_token,
        actual_attendees=actual_attendees,
        now_utc=now_utc,
    )


def sweep_study_space_reservations_service(
    db: Session,
    user: Optional[User] = None,
    now_utc: Optional[datetime] = None,
) -> ReservationSweepReport:
    """
    Idempotent lifecycle sweep:
    1. Active reservations where checked_in_at IS NULL and now >= start_time + NO_SHOW_GRACE_PERIOD_MINUTES
       transition to 'no_show'.
    2. Active reservations where checked_in_at IS NOT NULL and now >= end_time
       transition to 'completed'.
    Reservations without check-in evidence NEVER transition to 'completed'.
    Repeated sweeps produce idempotent results and never mutate already-transitioned rows.
    """
    if user is not None and user.role not in ("librarian", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to run reservation lifecycle sweeps.",
        )

    settings = get_settings()
    if now_utc is None:
        now_utc = normalize_utc_datetime(get_utc_now())
    else:
        now_utc = normalize_utc_datetime(now_utc)

    # 1. No-show sweep
    no_show_cutoff = now_utc - timedelta(minutes=settings.NO_SHOW_GRACE_PERIOD_MINUTES)
    due_no_shows = crud_spaces.get_reservations_due_for_no_show(db, cutoff_time=no_show_cutoff)
    no_show_ids: List[int] = []
    for res in due_no_shows:
        updated = crud_spaces.mark_reservation_no_show(db, res.id)
        if updated > 0:
            no_show_ids.append(res.id)

    # 2. Completion sweep (requires checked_in_at is not null)
    due_completions = crud_spaces.get_reservations_due_for_completion(db, now_time=now_utc)
    completed_ids: List[int] = []
    for res in due_completions:
        updated = crud_spaces.mark_reservation_completed(db, res.id)
        if updated > 0:
            completed_ids.append(res.id)

    try:
        db.flush()
    except (IntegrityError, OperationalError) as err:
        raise classify_spaces_db_exception(err, action="sweeping")

    logger.info(
        "Study space sweep completed at %s: %d marked no-show, %d marked completed.",
        now_utc,
        len(no_show_ids),
        len(completed_ids),
    )

    return ReservationSweepReport(
        processed_count=len(no_show_ids) + len(completed_ids),
        no_show_count=len(no_show_ids),
        completed_count=len(completed_ids),
        no_show_reservation_ids=no_show_ids,
        completed_reservation_ids=completed_ids,
    )

