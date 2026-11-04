"""
CRUD module for Study Space Occupancy Tracking, Telemetry & Analytics.
Provides efficient SQL aggregation queries and idempotent telemetry persistence.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import cast, func, select, Integer
from sqlalchemy.orm import Session

from app.models import OccupancyObservation, Reservation, StudyRoom, StudySeat, StudyZone


def get_current_zone_occupancy(db: Session, now: datetime) -> List[Dict]:
    """
    Computes real-time zone occupancy from active, checked-in seat reservations.
    Clamps counts to zone capacity and ensures available seats never fall below zero.
    """
    zones = (
        db.execute(
            select(StudyZone)
            .where(StudyZone.is_active.is_(True))
            .order_by(StudyZone.floor.asc(), StudyZone.id.asc())
        )
        .scalars()
        .all()
    )

    # Active, checked-in seat reservations currently underway
    seat_occ_stmt = (
        select(
            StudySeat.zone_id,
            func.count(func.distinct(Reservation.seat_id)).label("occupied_seats"),
        )
        .join(StudySeat, Reservation.seat_id == StudySeat.id)
        .where(
            Reservation.status == "active",
            Reservation.checked_in_at.is_not(None),
            Reservation.start_time <= now,
            Reservation.end_time > now,
            Reservation.resource_type == "seat",
        )
        .group_by(StudySeat.zone_id)
    )
    occ_by_zone = {row[0]: row[1] for row in db.execute(seat_occ_stmt).all()}

    results = []
    for zone in zones:
        occupied = min(zone.total_capacity, occ_by_zone.get(zone.id, 0))
        available = max(0, zone.total_capacity - occupied)
        util_pct = (
            round((occupied / zone.total_capacity) * 100.0, 2)
            if zone.total_capacity > 0
            else 0.0
        )
        results.append(
            {
                "zone_id": zone.id,
                "zone_code": zone.zone_code,
                "name": zone.name,
                "floor": zone.floor,
                "noise_policy": zone.noise_policy,
                "total_capacity": zone.total_capacity,
                "occupied_seats": occupied,
                "available_seats": available,
                "utilization_percentage": util_pct,
            }
        )

    return results


def get_current_room_occupancy(db: Session, now: datetime) -> List[Dict]:
    """
    Computes real-time room occupancy from active, checked-in room reservations.
    Uses actual_attendees when available (falling back to expected_attendees or 1),
    clamped to the room's configured maximum capacity.
    """
    rooms = (
        db.execute(
            select(StudyRoom)
            .where(StudyRoom.is_active.is_(True))
            .order_by(StudyRoom.room_code.asc())
        )
        .scalars()
        .all()
    )

    room_res_stmt = (
        select(Reservation)
        .where(
            Reservation.status == "active",
            Reservation.checked_in_at.is_not(None),
            Reservation.start_time <= now,
            Reservation.end_time > now,
            Reservation.resource_type == "room",
        )
    )
    res_by_room = {r.room_id: r for r in db.execute(room_res_stmt).scalars().all()}

    results = []
    for room in rooms:
        res = res_by_room.get(room.id)
        is_occupied = res is not None
        attendees = 0
        if is_occupied:
            raw_att = (
                res.actual_attendees
                if res.actual_attendees is not None
                else (res.expected_attendees or 1)
            )
            attendees = max(1, min(room.capacity, raw_att))

        results.append(
            {
                "room_id": room.id,
                "room_code": room.room_code,
                "name": room.name,
                "capacity": room.capacity,
                "display_type": room.display_type,
                "has_whiteboard": room.has_whiteboard,
                "is_active": room.is_active,
                "is_occupied": is_occupied,
                "current_attendees": attendees,
                "active_reservation_id": res.id if res else None,
            }
        )

    return results


def get_seat_amenities_breakdown(db: Session) -> Dict[str, int]:
    """
    Returns counts of active seats equipped with power outlets, monitors, or accessibility features.
    """
    stmt = select(
        func.count(StudySeat.id).label("total"),
        func.sum(cast(StudySeat.has_power_outlet, Integer)).label("power"),
        func.sum(cast(StudySeat.has_monitor, Integer)).label("monitor"),
        func.sum(cast(StudySeat.is_accessible, Integer)).label("accessible"),
    ).where(StudySeat.is_active.is_(True))

    row = db.execute(stmt).first()
    if not row:
        return {"total": 0, "power": 0, "monitor": 0, "accessible": 0}

    return {
        "total": row.total or 0,
        "power": row.power or 0,
        "monitor": row.monitor or 0,
        "accessible": row.accessible or 0,
    }


def get_historical_occupancy(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    zone_id: Optional[int] = None,
    interval: str = "day",
) -> Dict:
    """
    Aggregates historical occupancy observations by time bucket (hourly or daily)
    directly within SQL to avoid loading large observation sets into memory.
    """
    if interval == "hour":
        bucket_expr = func.strftime("%Y-%m-%d %H:00", OccupancyObservation.recorded_at)
    else:
        bucket_expr = func.strftime("%Y-%m-%d", OccupancyObservation.recorded_at)

    filters = [
        OccupancyObservation.recorded_at >= start_date,
        OccupancyObservation.recorded_at <= end_date,
    ]
    if zone_id is not None:
        filters.append(OccupancyObservation.zone_id == zone_id)

    # Aggregated data points
    bucket_stmt = (
        select(
            bucket_expr.label("time_bucket"),
            func.avg(OccupancyObservation.observed_count).label("avg_occ"),
            func.max(OccupancyObservation.observed_count).label("max_occ"),
            func.min(OccupancyObservation.observed_count).label("min_occ"),
            func.avg(OccupancyObservation.capacity_utilization).label("avg_util"),
            func.count(OccupancyObservation.id).label("obs_cnt"),
        )
        .where(*filters)
        .group_by("time_bucket")
        .order_by(bucket_expr.asc())
    )
    bucket_rows = db.execute(bucket_stmt).all()

    # Overall summary stats
    summary_stmt = select(
        func.count(OccupancyObservation.id).label("total_cnt"),
        func.avg(OccupancyObservation.observed_count).label("avg_occ"),
        func.max(OccupancyObservation.observed_count).label("max_occ"),
        func.avg(OccupancyObservation.capacity_utilization).label("avg_util"),
    ).where(*filters)
    sum_row = db.execute(summary_stmt).first()

    data_points = [
        {
            "time_bucket": r[0],
            "zone_id": zone_id,
            "avg_observed_count": round(float(r[1] or 0.0), 2),
            "max_observed_count": int(r[2] or 0),
            "min_observed_count": int(r[3] or 0),
            "avg_capacity_utilization": round(float(r[4] or 0.0), 4),
            "observation_count": int(r[5] or 0),
        }
        for r in bucket_rows
    ]

    total_obs = int(sum_row.total_cnt or 0) if sum_row else 0
    avg_occ = round(float(sum_row.avg_occ or 0.0), 2) if sum_row else 0.0
    peak_occ = int(sum_row.max_occ or 0) if sum_row and sum_row.max_occ is not None else 0
    avg_util = round(float(sum_row.avg_util or 0.0), 4) if sum_row else 0.0

    return {
        "interval": interval,
        "zone_id": zone_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_observations": total_obs,
        "overall_avg_occupancy": avg_occ,
        "overall_peak_occupancy": peak_occ,
        "overall_avg_utilization": avg_util,
        "data_points": data_points,
    }


def get_peak_usage_hours(
    db: Session,
    zone_id: Optional[int] = None,
    days_back: int = 30,
    as_of: Optional[datetime] = None,
) -> Dict:
    """
    Computes hourly distribution (0-23) of occupancy over the trailing days_back period.
    Identifies peak hours with highest average utilization.
    """
    if as_of is None:
        # Detect latest observation time if available
        latest_dt = db.execute(select(func.max(OccupancyObservation.recorded_at))).scalar()
        as_of = latest_dt if latest_dt is not None else datetime.utcnow()

    start_date = as_of - timedelta(days=days_back)
    filters = [
        OccupancyObservation.recorded_at >= start_date,
        OccupancyObservation.recorded_at <= as_of,
    ]
    if zone_id is not None:
        filters.append(OccupancyObservation.zone_id == zone_id)

    hour_expr = cast(func.strftime("%H", OccupancyObservation.recorded_at), Integer)

    stmt = (
        select(
            hour_expr.label("hour_of_day"),
            func.avg(OccupancyObservation.observed_count).label("avg_occ"),
            func.max(OccupancyObservation.observed_count).label("max_occ"),
            func.avg(OccupancyObservation.capacity_utilization).label("avg_util"),
            func.count(OccupancyObservation.id).label("obs_cnt"),
        )
        .where(*filters)
        .group_by(hour_expr)
        .order_by(hour_expr.asc())
    )
    rows = db.execute(stmt).all()

    # Build 0-23 map
    row_map = {int(r[0]): r for r in rows if r[0] is not None}
    distribution = []
    max_avg_occ = -1.0
    peak_hr = 12
    min_avg_occ = float("inf")
    lowest_hr = 0
    total_obs = 0

    for h in range(24):
        if h in row_map:
            r = row_map[h]
            avg_occ = round(float(r[1] or 0.0), 2)
            max_occ = int(r[2] or 0)
            avg_util = round(float(r[3] or 0.0) * 100.0, 2)
            cnt = int(r[4] or 0)
            total_obs += cnt
        else:
            avg_occ = 0.0
            max_occ = 0
            avg_util = 0.0
            cnt = 0

        if avg_occ > max_avg_occ:
            max_avg_occ = avg_occ
            peak_hr = h
        if cnt > 0 and avg_occ < min_avg_occ:
            min_avg_occ = avg_occ
            lowest_hr = h

        distribution.append(
            {
                "hour_of_day": h,
                "avg_observed_count": avg_occ,
                "peak_observed_count": max_occ,
                "avg_utilization_percentage": avg_util,
                "observation_count": cnt,
                "is_peak": False,
            }
        )

    # Flag peak hour
    for d in distribution:
        if d["hour_of_day"] == peak_hr and max_avg_occ > 0:
            d["is_peak"] = True

    return {
        "zone_id": zone_id,
        "days_analyzed": days_back,
        "total_observations": total_obs,
        "peak_hour": peak_hr,
        "peak_hour_avg_occupancy": max(0.0, max_avg_occ),
        "lowest_hour": lowest_hr if min_avg_occ != float("inf") else 0,
        "hourly_distribution": distribution,
    }


def get_latest_observation_time(db: Session) -> Optional[datetime]:
    """Returns the most recent recorded observation timestamp in the database."""
    return db.execute(select(func.max(OccupancyObservation.recorded_at))).scalar()


def find_existing_observation(
    db: Session, zone_id: int, recorded_at: datetime
) -> Optional[OccupancyObservation]:
    """Finds an observation matching exact zone_id and recorded_at timestamp."""
    stmt = select(OccupancyObservation).where(
        OccupancyObservation.zone_id == zone_id,
        OccupancyObservation.recorded_at == recorded_at,
    )
    return db.execute(stmt).scalars().first()


def save_telemetry_observation(
    db: Session,
    zone_id: int,
    observed_count: int,
    capacity_utilization: float,
    recorded_at: datetime,
    source_sensor_id: Optional[str] = None,
) -> Tuple[OccupancyObservation, str]:
    """
    Idempotently records a telemetry observation.
    - If duplicate observation exists with same count/sensor, returns existing with 'idempotent_duplicate'.
    - If duplicate exists with different count, updates it with 'updated'.
    - Otherwise inserts new record with 'recorded'.
    """
    existing = find_existing_observation(db=db, zone_id=zone_id, recorded_at=recorded_at)
    if existing is not None:
        if (
            existing.observed_count == observed_count
            and existing.source_sensor_id == source_sensor_id
        ):
            return existing, "idempotent_duplicate"
        existing.observed_count = observed_count
        existing.capacity_utilization = capacity_utilization
        existing.source_sensor_id = source_sensor_id
        db.flush()
        return existing, "updated"

    new_obs = OccupancyObservation(
        zone_id=zone_id,
        recorded_at=recorded_at,
        observed_count=observed_count,
        capacity_utilization=capacity_utilization,
        source_sensor_id=source_sensor_id,
    )
    db.add(new_obs)
    db.flush()
    return new_obs, "recorded"

