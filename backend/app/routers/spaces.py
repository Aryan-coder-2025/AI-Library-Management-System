"""
Study space reservations API router.
Provides endpoints for creating, retrieving, cancelling, and querying study space reservations.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user, require_role
from app.models import User
from app.schemas import (
    CurrentOccupancyResponse,
    HistoricalOccupancyResponse,
    PeakUsageAnalysisResponse,
    ReservationCheckInRequest,
    ReservationCheckInWithTokenRequest,
    ReservationCreate,
    ReservationPaginationResponse,
    ReservationQRResponse,
    ReservationResponse,
    ReservationSweepReport,
    ResourceOccupancyResponse,
    SpaceAvailabilityResponse,
    StudyZoneResponse,
    TelemetryObservationCreate,
    TelemetryObservationResponse,
    ZoneOccupancySummary,
)
from app.services import spaces as space_service
from app.services import occupancy as occupancy_service

router = APIRouter(prefix="/api/spaces", tags=["Study Spaces"])


@router.get("/zones", response_model=List[StudyZoneResponse])
def list_zones(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lists all active study zones."""
    return space_service.get_study_zones_service(db=db)


@router.get("/availability", response_model=SpaceAvailabilityResponse)
def check_availability(
    start_time: datetime = Query(..., description="Start of interval in ISO format (UTC)"),
    end_time: datetime = Query(..., description="End of interval in ISO format (UTC)"),
    resource_type: Optional[str] = Query(None, pattern="^(seat|room)$"),
    zone_id: Optional[int] = Query(None, description="Optional zone ID filter for seats"),
    min_capacity: Optional[int] = Query(None, ge=1, description="Minimum room capacity filter"),
    has_power: Optional[bool] = Query(None, description="Power outlet filter for seats"),
    has_monitor: Optional[bool] = Query(None, description="Monitor filter for seats"),
    is_accessible: Optional[bool] = Query(None, description="Accessibility filter for seats"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Queries real-time availability of seats and rooms over the requested time window.
    Guarantees privacy: does not expose booking user details.
    """
    return space_service.query_space_availability_service(
        db=db,
        start_time=start_time,
        end_time=end_time,
        resource_type=resource_type,
        zone_id=zone_id,
        min_capacity=min_capacity,
        has_power=has_power,
        has_monitor=has_monitor,
        is_accessible=is_accessible,
    )


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    payload: ReservationCreate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Creates a new study space reservation.
    Serializes through BEGIN IMMEDIATE write transaction, enforcing quotas,
    operating hours, and overlap prevention.
    """
    return space_service.create_reservation_service(
        db=db,
        user=current_user,
        data=payload,
    )


@router.get("/reservations/my", response_model=ReservationPaginationResponse)
@router.get("/reservations/me", response_model=ReservationPaginationResponse)
def get_my_reservations(
    status: Optional[str] = Query(None, pattern="^(active|completed|cancelled|no_show)$"),
    status_filter: Optional[str] = Query(None, pattern="^(active|completed|cancelled|no_show)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieves paginated reservations for the authenticated patron."""
    effective_status = status_filter or status
    return space_service.get_my_reservations_service(
        db=db,
        user=current_user,
        status_filter=effective_status,
        page=page,
        page_size=page_size,
    )


@router.get("/reservations", response_model=ReservationPaginationResponse)
@router.get("/reservations/all", response_model=ReservationPaginationResponse)
def list_all_reservations(
    user_id: Optional[int] = Query(None, description="Filter by patron ID"),
    status: Optional[str] = Query(None, pattern="^(active|completed|cancelled|no_show)$"),
    status_filter: Optional[str] = Query(None, pattern="^(active|completed|cancelled|no_show)$"),
    resource_type: Optional[str] = Query(None, pattern="^(seat|room)$"),
    start_date: Optional[datetime] = Query(None, description="Filter reservations starting on or after"),
    end_date: Optional[datetime] = Query(None, description="Filter reservations ending on or before"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """
    Lists reservations across all patrons. Restricted to librarians and administrators.
    """
    effective_status = status_filter or status
    return space_service.get_all_reservations_service(
        db=db,
        user=current_user,
        user_id=user_id,
        status_filter=effective_status,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves details of a specific reservation.
    Allowed for the reservation owner or librarians/admins.
    """
    return space_service.get_reservation_service(
        db=db,
        user=current_user,
        reservation_id=reservation_id,
    )


@router.delete("/reservations/{reservation_id}", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cancels an active reservation.
    """
    return space_service.cancel_reservation_service(
        db=db,
        user=current_user,
        reservation_id=reservation_id,
    )


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation_post(
    reservation_id: int,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cancels an active reservation (POST alias).
    """
    return space_service.cancel_reservation_service(
        db=db,
        user=current_user,
        reservation_id=reservation_id,
    )


@router.get("/reservations/{reservation_id}/qr", response_model=ReservationQRResponse)
def get_reservation_qr_token(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves a cryptographically signed QR check-in token and metadata for a reservation.
    Only the reservation owner or librarians/admins can obtain the QR token.
    """
    return space_service.get_reservation_qr_token_service(
        db=db,
        user=current_user,
        reservation_id=reservation_id,
    )


@router.post("/reservations/{reservation_id}/check-in", response_model=ReservationResponse)
def check_in_reservation(
    reservation_id: int,
    payload: Optional[ReservationCheckInRequest] = None,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Checks in an active study space reservation.
    Validates check-in window and grace periods, attendee limits, and enforces atomic check-in.
    """
    actual_attendees = payload.actual_attendees if payload else None
    return space_service.check_in_reservation_service(
        db=db,
        user=current_user,
        reservation_id=reservation_id,
        actual_attendees=actual_attendees,
    )


@router.post("/reservations/check-in-by-token", response_model=ReservationResponse)
def check_in_by_token(
    payload: ReservationCheckInWithTokenRequest,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Checks in a reservation using a scanned QR check-in token.
    Validates token authenticity, expiration, and user authorization.
    """
    return space_service.check_in_by_qr_token_service(
        db=db,
        user=current_user,
        qr_token=payload.token,
        actual_attendees=payload.actual_attendees,
    )


@router.post("/reservations/sweep", response_model=ReservationSweepReport)
def sweep_reservations(
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """
    Executes an administrative lifecycle sweep:
    - Marks un-checked-in reservations past their grace period as 'no_show'.
    - Marks checked-in reservations past their scheduled end time as 'completed'.
    """
    return space_service.sweep_study_space_reservations_service(
        db=db,
        user=current_user,
    )


# ── Stage 10.4: Occupancy Tracking, Telemetry & Analytics Endpoints ───────────

@router.get("/occupancy/current", response_model=CurrentOccupancyResponse)
def get_current_occupancy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves real-time library occupancy summary across all study zones and rooms.
    Strictly derives live occupancy from active, checked-in reservations.
    Excludes patron identities and personal reservation details.
    """
    return occupancy_service.calculate_live_occupancy(db=db)


@router.get("/occupancy/zones", response_model=List[ZoneOccupancySummary])
def get_zone_occupancy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves current occupancy, capacity, and utilization percentage per study zone.
    Excludes patron identities and personal reservation details.
    """
    return occupancy_service.get_zone_occupancy_breakdown(db=db)


@router.get("/occupancy/resources", response_model=ResourceOccupancyResponse)
def get_resource_occupancy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves detailed breakdown of seat and study room utilization.
    Includes amenity counts (power, monitor, accessibility) and room attendee tallies.
    """
    return occupancy_service.get_resource_occupancy_breakdown(db=db)


@router.get("/occupancy/historical", response_model=HistoricalOccupancyResponse)
def get_historical_occupancy(
    start_date: Optional[datetime] = Query(None, description="Start datetime (UTC) for historical query"),
    end_date: Optional[datetime] = Query(None, description="End datetime (UTC) for historical query"),
    days_back: Optional[int] = Query(None, ge=1, le=366, description="Trailing lookback days relative to end_date or latest observation"),
    zone_id: Optional[int] = Query(None, description="Optional zone ID filter"),
    interval: str = Query("day", description="Aggregation bucket interval: 'day' or 'hour'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves aggregated historical occupancy trends from telemetry observations.
    Aggregates within SQL to prevent loading observation tables into application memory.
    """
    return occupancy_service.get_historical_occupancy_service(
        db=db,
        start_date=start_date,
        end_date=end_date,
        days_back=days_back,
        zone_id=zone_id,
        interval=interval,
    )


@router.get("/occupancy/peak-hours", response_model=PeakUsageAnalysisResponse)
def get_peak_usage_hours(
    zone_id: Optional[int] = Query(None, description="Optional zone ID filter"),
    days_back: int = Query(30, ge=1, le=366, description="Trailing number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Analyzes historical occupancy observations to identify peak usage hours (0-23)
    and hourly utilization distribution across the specified trailing period.
    """
    return occupancy_service.get_peak_usage_service(
        db=db,
        zone_id=zone_id,
        days_back=days_back,
    )


@router.post(
    "/occupancy/telemetry",
    response_model=TelemetryObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_telemetry_observation(
    payload: TelemetryObservationCreate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """
    Ingests an occupancy telemetry observation idempotently.
    Requires librarian or admin authorization.
    Validates zone existence and non-negative headcount; computes capacity utilization.
    """
    return occupancy_service.ingest_telemetry_observation(
        db=db,
        payload=payload,
    )


