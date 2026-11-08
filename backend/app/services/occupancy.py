"""
Service module for Study Space Occupancy Tracking, Telemetry & Analytics.
Coordinates business logic, metric calculations, and safe boundary enforcement.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import occupancy as crud_occupancy
from app.models import StudyZone
from app.schemas import (
    CurrentOccupancyResponse,
    HistoricalOccupancyDataPoint,
    HistoricalOccupancyResponse,
    PeakUsageAnalysisResponse,
    PeakUsageHourSummary,
    ResourceOccupancyResponse,
    ResourceRoomBreakdown,
    ResourceSeatBreakdown,
    RoomOccupancySummary,
    TelemetryObservationCreate,
    TelemetryObservationResponse,
    ZoneOccupancySummary,
)
from app.utils.date import get_utc_now


def _ensure_naive_utc(dt: datetime) -> datetime:
    """Ensures a datetime is naive UTC for consistent SQLite querying."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def calculate_live_occupancy(
    db: Session, as_of: Optional[datetime] = None
) -> CurrentOccupancyResponse:
    """
    Computes real-time library occupancy across all zones and study rooms.
    Strictly derives live occupancy from active, checked-in reservations.
    - Seats with check-in count as 1 occupant.
    - Rooms with check-in count as actual_attendees (or expected_attendees fallback).
    - Unchecked-in, cancelled, completed, or no-show reservations are excluded.
    - Double counting is strictly prevented and metrics are clamped to capacities.
    """
    now = _ensure_naive_utc(as_of) if as_of is not None else get_utc_now()

    zones_raw = crud_occupancy.get_current_zone_occupancy(db=db, now=now)
    rooms_raw = crud_occupancy.get_current_room_occupancy(db=db, now=now)

    zones_summary = [ZoneOccupancySummary(**z) for z in zones_raw]
    rooms_summary = [RoomOccupancySummary(**r) for r in rooms_raw]

    occupied_seats = sum(z.occupied_seats for z in zones_summary)
    total_seats = sum(z.total_capacity for z in zones_summary)
    seat_util = (
        round((occupied_seats / total_seats) * 100.0, 2) if total_seats > 0 else 0.0
    )

    occupied_room_att = sum(r.current_attendees for r in rooms_summary)
    total_room_cap = sum(r.capacity for r in rooms_summary)
    room_att_util = (
        round((occupied_room_att / total_room_cap) * 100.0, 2)
        if total_room_cap > 0
        else 0.0
    )
    active_rooms = sum(1 for r in rooms_summary if r.is_occupied)
    total_rooms = len(rooms_summary)

    total_lib_occ = occupied_seats + occupied_room_att
    total_lib_cap = total_seats + total_room_cap
    total_lib_avail = max(0, total_lib_cap - total_lib_occ)
    overall_util = (
        round((total_lib_occ / total_lib_cap) * 100.0, 2) if total_lib_cap > 0 else 0.0
    )

    return CurrentOccupancyResponse(
        total_library_occupancy=total_lib_occ,
        total_library_capacity=total_lib_cap,
        total_library_available=total_lib_avail,
        overall_utilization_percentage=min(100.0, overall_util),
        occupied_seats=occupied_seats,
        total_seats=total_seats,
        seat_utilization_percentage=min(100.0, seat_util),
        occupied_room_attendees=occupied_room_att,
        total_room_capacity=total_room_cap,
        room_attendees_utilization_percentage=min(100.0, room_att_util),
        active_rooms_count=active_rooms,
        total_rooms_count=total_rooms,
        zones=zones_summary,
        rooms=rooms_summary,
        provenance="reservation_estimate",
        as_of=now,
    )


def get_zone_occupancy_breakdown(
    db: Session, as_of: Optional[datetime] = None
) -> List[ZoneOccupancySummary]:
    """Returns zone-by-zone current occupancy breakdown."""
    now = _ensure_naive_utc(as_of) if as_of is not None else get_utc_now()
    raw = crud_occupancy.get_current_zone_occupancy(db=db, now=now)
    return [ZoneOccupancySummary(**z) for z in raw]


def get_resource_occupancy_breakdown(
    db: Session, as_of: Optional[datetime] = None
) -> ResourceOccupancyResponse:
    """Returns detailed seat amenities and study room utilization breakdown."""
    now = _ensure_naive_utc(as_of) if as_of is not None else get_utc_now()

    zones_raw = crud_occupancy.get_current_zone_occupancy(db=db, now=now)
    rooms_raw = crud_occupancy.get_current_room_occupancy(db=db, now=now)
    amenities = crud_occupancy.get_seat_amenities_breakdown(db=db)

    occupied_seats = sum(z["occupied_seats"] for z in zones_raw)
    total_seats = sum(z["total_capacity"] for z in zones_raw)
    avail_seats = max(0, total_seats - occupied_seats)
    seat_util = (
        round((occupied_seats / total_seats) * 100.0, 2) if total_seats > 0 else 0.0
    )

    occupied_room_att = sum(r["current_attendees"] for r in rooms_raw)
    total_room_cap = sum(r["capacity"] for r in rooms_raw)
    avail_room_cap = max(0, total_room_cap - occupied_room_att)
    room_util = (
        round((occupied_room_att / total_room_cap) * 100.0, 2)
        if total_room_cap > 0
        else 0.0
    )
    active_rooms = sum(1 for r in rooms_raw if r["is_occupied"])

    seat_breakdown = ResourceSeatBreakdown(
        total_seats=total_seats,
        occupied_seats=occupied_seats,
        available_seats=avail_seats,
        utilization_percentage=min(100.0, seat_util),
        power_outlet_seats_count=amenities["power"],
        monitor_seats_count=amenities["monitor"],
        accessible_seats_count=amenities["accessible"],
    )

    room_breakdown = ResourceRoomBreakdown(
        total_rooms=len(rooms_raw),
        active_occupied_rooms=active_rooms,
        total_room_capacity=total_room_cap,
        occupied_room_attendees=occupied_room_att,
        available_room_capacity=avail_room_cap,
        utilization_percentage=min(100.0, room_util),
        rooms=[RoomOccupancySummary(**r) for r in rooms_raw],
    )

    return ResourceOccupancyResponse(
        seats=seat_breakdown,
        rooms=room_breakdown,
        provenance="reservation_estimate",
        as_of=now,
    )


def get_historical_occupancy_service(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    days_back: Optional[int] = None,
    zone_id: Optional[int] = None,
    interval: str = "day",
) -> HistoricalOccupancyResponse:
    """
    Validates query parameters and computes historical occupancy trends
    using optimized database aggregation.
    """
    if interval not in ("hour", "day"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interval must be 'hour' or 'day'.",
        )

    if days_back is not None and (days_back < 1 or days_back > 366):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="days_back must be between 1 and 366.",
        )

    if zone_id is not None:
        zone = db.get(StudyZone, zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Study zone ID {zone_id} not found.",
            )

    # Resolve date boundaries
    if end_date is None:
        latest = crud_occupancy.get_latest_observation_time(db)
        resolved_end = latest if latest is not None else get_utc_now()
    else:
        resolved_end = _ensure_naive_utc(end_date)

    if start_date is None:
        lookback = days_back if days_back is not None else (30 if interval == "day" else 7)
        resolved_start = resolved_end - timedelta(days=lookback)
    else:
        resolved_start = _ensure_naive_utc(start_date)

    if resolved_start > resolved_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be earlier than or equal to end_date.",
        )

    if (resolved_end - resolved_start).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 366 days.",
        )

    res = crud_occupancy.get_historical_occupancy(
        db=db,
        start_date=resolved_start,
        end_date=resolved_end,
        zone_id=zone_id,
        interval=interval,
    )

    return HistoricalOccupancyResponse(
        interval=res["interval"],
        zone_id=res["zone_id"],
        start_date=res["start_date"],
        end_date=res["end_date"],
        total_observations=res["total_observations"],
        overall_avg_occupancy=res["overall_avg_occupancy"],
        overall_peak_occupancy=res["overall_peak_occupancy"],
        overall_avg_utilization=res["overall_avg_utilization"],
        data_points=[HistoricalOccupancyDataPoint(**dp) for dp in res["data_points"]],
        provenance="recorded_telemetry",
    )


def get_peak_usage_service(
    db: Session, zone_id: Optional[int] = None, days_back: int = 30
) -> PeakUsageAnalysisResponse:
    """
    Validates inputs and computes peak usage periods and hourly distribution.
    """
    if days_back < 1 or days_back > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="days_back must be between 1 and 366.",
        )

    if zone_id is not None:
        zone = db.get(StudyZone, zone_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Study zone ID {zone_id} not found.",
            )

    latest = crud_occupancy.get_latest_observation_time(db)
    as_of = latest if latest is not None else get_utc_now()

    res = crud_occupancy.get_peak_usage_hours(
        db=db, zone_id=zone_id, days_back=days_back, as_of=as_of
    )

    return PeakUsageAnalysisResponse(
        zone_id=res["zone_id"],
        days_analyzed=res["days_analyzed"],
        total_observations=res["total_observations"],
        peak_hour=res["peak_hour"],
        peak_hour_avg_occupancy=res["peak_hour_avg_occupancy"],
        lowest_hour=res["lowest_hour"],
        hourly_distribution=[PeakUsageHourSummary(**h) for h in res["hourly_distribution"]],
        provenance="recorded_telemetry",
    )


def ingest_telemetry_observation(
    db: Session, payload: TelemetryObservationCreate
) -> TelemetryObservationResponse:
    """
    Ingests an occupancy telemetry observation idempotently.
    Validates zone existence, active status, and non-negative headcount.
    Safe against divide-by-zero on zero-capacity zones.
    """
    zone = db.get(StudyZone, payload.zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study zone ID {payload.zone_id} not found.",
        )

    if not zone.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Study zone '{zone.zone_code}' is currently inactive.",
        )

    if payload.observed_count < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="observed_count must be a non-negative integer.",
        )

    # Plausibility threshold: allow reasonable overflow (e.g. standing/crowding),
    # but reject implausible sensor spikes exceeding 3x capacity.
    # Floor capacity at 20 for small or zero capacity zones.
    max_credible_count = max(int(zone.total_capacity * 3.0), 20)
    if payload.observed_count > max_credible_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"observed_count ({payload.observed_count}) exceeds plausible sensor threshold ({max_credible_count}) for zone '{zone.zone_code}'.",
        )

    # Timestamp validation:
    # 1. Reject future timestamps beyond 10-minute clock skew.
    # 2. Allow historical timestamps up to 5 years in the past for backfill/seeding.
    # 3. When omitted (None), pass None to save_telemetry_observation to enable
    #    sliding-window (15s) rapid-retry deduplication without clobbering independent readings.
    now_naive = _ensure_naive_utc(get_utc_now())
    if payload.recorded_at is not None:
        recorded_dt = _ensure_naive_utc(payload.recorded_at)
        max_allowed_future = now_naive + timedelta(minutes=10)
        if recorded_dt > max_allowed_future:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recorded_at cannot be in the future beyond acceptable sensor clock skew (10 minutes).",
            )
        if recorded_dt < now_naive - timedelta(days=365 * 5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recorded_at is too far in the past (maximum 5 years).",
            )
    else:
        recorded_dt = None

    util = (
        round(float(payload.observed_count) / float(zone.total_capacity), 4)
        if zone.total_capacity > 0
        else 0.0
    )

    obs, status_str = crud_occupancy.save_telemetry_observation(
        db=db,
        zone_id=zone.id,
        observed_count=payload.observed_count,
        capacity_utilization=util,
        recorded_at=recorded_dt,
        source_sensor_id=payload.source_sensor_id,
        idempotency_window_seconds=15,
    )
    db.flush()

    return TelemetryObservationResponse(
        id=obs.id,
        zone_id=obs.zone_id,
        recorded_at=obs.recorded_at,
        observed_count=obs.observed_count,
        capacity_utilization=obs.capacity_utilization,
        source_sensor_id=obs.source_sensor_id,
        status=status_str,
    )
