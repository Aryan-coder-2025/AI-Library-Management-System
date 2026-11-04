"""Deterministic synthetic reservation generator for AI Library Management System.

Generates exactly 3,000 reservations:
- 2,400 Seat Reservations (seats 1..150)
- 600 Room Reservations (rooms 1..10)

Exact status distribution:
- 100 active (80 seat, 20 room)
- 2,650 completed (2,120 seat, 530 room)
- 180 cancelled (144 seat, 36 room)
- 70 no_show (56 seat, 14 room)
Total = 3,000 reservations.

Enforces:
- Schema constraints: end_time > start_time, mutually exclusive seat_id / room_id
- Permitted statuses: 'active', 'completed', 'cancelled', 'no_show'
- Strict interval conflict prevention: Active reservations on the same seat or room
  NEVER overlap in time, conforming strictly with database triggers.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple

from app.seed_data.generator import SeederConfig, get_namespace_rng
from app.seed_data.users_generator import SyntheticUser
from app.seed_data.spaces_generator import SyntheticStudySeat, SyntheticStudyRoom

logger = logging.getLogger(__name__)


@dataclass
class SyntheticReservation:
    id: int
    user_id: int
    resource_type: str  # 'seat' or 'room'
    seat_id: Optional[int]
    room_id: Optional[int]
    start_time: datetime
    end_time: datetime
    status: str  # 'active', 'completed', 'cancelled', 'no_show'
    created_at: datetime


def generate_reservations(
    config: SeederConfig,
    users: List[SyntheticUser],
    seats: List[SyntheticStudySeat],
    rooms: List[SyntheticStudyRoom],
) -> List[SyntheticReservation]:
    """
    Generates exactly 3,000 reservations (2,400 seat, 600 room) deterministically
    with exact status counts: 100 active, 2,650 completed, 180 cancelled, 70 no_show.
    """
    rng = get_namespace_rng(config.base_seed, "reservations")
    as_of = config.as_of
    sim_start = as_of - timedelta(days=60)

    # Borrowers eligible to reserve (students and teachers)
    borrower_ids = [u.id for u in users if u.role in ("student", "teacher")]

    reservations: List[SyntheticReservation] = []
    res_id = 1

    # ── 1. 2,400 SEAT RESERVATIONS ───────────────────────────────────────────
    # Status breakdown: 80 active, 2,120 completed, 144 cancelled, 56 no_show

    # 1a. 80 Active Seat Reservations (assigned to 80 distinct seats to guarantee 0 conflicts)
    active_seats = seats[:80]
    for s in active_seats:
        u_id = rng.choice(borrower_ids)
        # Scheduled near or after as_of (active at as_of or upcoming in next 3 days)
        day_offset = rng.uniform(0.1, 3.0)
        start_dt = as_of + timedelta(days=day_offset)
        duration_hours = rng.choice([1, 2, 3, 4])
        end_dt = start_dt + timedelta(hours=duration_hours)
        created_dt = start_dt - timedelta(days=rng.randint(1, 4), hours=rng.randint(1, 10))

        reservations.append(
            SyntheticReservation(
                id=res_id,
                user_id=u_id,
                resource_type="seat",
                seat_id=s.id,
                room_id=None,
                start_time=start_dt,
                end_time=end_dt,
                status="active",
                created_at=created_dt,
            )
        )
        res_id += 1

    # 1b. 2,120 Completed Seat Reservations (strictly in the past: end_time <= as_of)
    for _ in range(2120):
        u_id = rng.choice(borrower_ids)
        s = rng.choice(seats)
        offset_days = rng.uniform(-59.0, -0.5)
        day_base = (as_of + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_hour = rng.randint(8, 18)
        start_minute = rng.choice([0, 15, 30, 45])
        start_dt = day_base + timedelta(hours=start_hour, minutes=start_minute)
        duration_hours = rng.choice([1, 2, 3, 4])
        end_dt = start_dt + timedelta(hours=duration_hours)
        created_dt = start_dt - timedelta(days=rng.randint(1, 7))

        reservations.append(
            SyntheticReservation(
                id=res_id,
                user_id=u_id,
                resource_type="seat",
                seat_id=s.id,
                room_id=None,
                start_time=start_dt,
                end_time=end_dt,
                status="completed",
                created_at=created_dt,
            )
        )
        res_id += 1

    # 1c. 144 Cancelled Seat Reservations
    for _ in range(144):
        u_id = rng.choice(borrower_ids)
        s = rng.choice(seats)
        offset_days = rng.uniform(-59.0, 5.0)
        day_base = (as_of + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_hour = rng.randint(8, 18)
        start_dt = day_base + timedelta(hours=start_hour)
        duration_hours = rng.choice([1, 2, 3])
        end_dt = start_dt + timedelta(hours=duration_hours)
        created_dt = start_dt - timedelta(days=rng.randint(1, 7))

        reservations.append(
            SyntheticReservation(
                id=res_id,
                user_id=u_id,
                resource_type="seat",
                seat_id=s.id,
                room_id=None,
                start_time=start_dt,
                end_time=end_dt,
                status="cancelled",
                created_at=created_dt,
            )
        )
        res_id += 1

    # 1d. 56 No-show Seat Reservations
    for _ in range(56):
        u_id = rng.choice(borrower_ids)
        s = rng.choice(seats)
        offset_days = rng.uniform(-59.0, -0.2)
        day_base = (as_of + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_hour = rng.randint(8, 18)
        start_dt = day_base + timedelta(hours=start_hour)
        duration_hours = rng.choice([1, 2])
        end_dt = start_dt + timedelta(hours=duration_hours)
        created_dt = start_dt - timedelta(days=rng.randint(1, 5))

        reservations.append(
            SyntheticReservation(
                id=res_id,
                user_id=u_id,
                resource_type="seat",
                seat_id=s.id,
                room_id=None,
                start_time=start_dt,
                end_time=end_dt,
                status="no_show",
                created_at=created_dt,
            )
        )
        res_id += 1

    # ── 2. 600 ROOM RESERVATIONS ─────────────────────────────────────────────
    # Status breakdown: 20 active, 530 completed, 36 cancelled, 14 no_show

    # 2a. 20 Active Room Reservations (2 per room on distinct days to guarantee 0 conflicts)
    for r in rooms:
        for day_slot in [1, 2]:
            u_id = rng.choice(borrower_ids)
            day_base = (as_of + timedelta(days=day_slot)).replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = day_base + timedelta(hours=10)
            end_dt = start_dt + timedelta(hours=2)
            created_dt = start_dt - timedelta(days=rng.randint(1, 3))

            reservations.append(
                SyntheticReservation(
                    id=res_id,
                    user_id=u_id,
                    resource_type="room",
                    seat_id=None,
                    room_id=r.id,
                    start_time=start_dt,
                    end_time=end_dt,
                    status="active",
                    created_at=created_dt,
                )
            )
            res_id += 1

    # 2b. 530 Completed Room Reservations (strictly in the past)
    for _ in range(530):
        u_id = rng.choice(borrower_ids)
        r = rng.choice(rooms)
        offset_days = rng.uniform(-59.0, -0.5)
        day_base = (as_of + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_hour = rng.randint(9, 17)
        start_dt = day_base + timedelta(hours=start_hour)
        duration_hours = rng.choice([1, 2, 3])
        end_dt = start_dt + timedelta(hours=duration_hours)
        created_dt = start_dt - timedelta(days=rng.randint(2, 7))

        reservations.append(
            SyntheticReservation(
                id=res_id,
                user_id=u_id,
                resource_type="room",
                seat_id=None,
                room_id=r.id,
                start_time=start_dt,
                end_time=end_dt,
                status="completed",
                created_at=created_dt,
            )
        )
        res_id += 1

    # 2c. 36 Cancelled Room Reservations
    for _ in range(36):
        u_id = rng.choice(borrower_ids)
        r = rng.choice(rooms)
        offset_days = rng.uniform(-59.0, 5.0)
        day_base = (as_of + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_hour = rng.randint(9, 17)
        start_dt = day_base + timedelta(hours=start_hour)
        duration_hours = rng.choice([1, 2])
        end_dt = start_dt + timedelta(hours=duration_hours)
        created_dt = start_dt - timedelta(days=rng.randint(2, 7))

        reservations.append(
            SyntheticReservation(
                id=res_id,
                user_id=u_id,
                resource_type="room",
                seat_id=None,
                room_id=r.id,
                start_time=start_dt,
                end_time=end_dt,
                status="cancelled",
                created_at=created_dt,
            )
        )
        res_id += 1

    # 2d. 14 No-show Room Reservations
    for _ in range(14):
        u_id = rng.choice(borrower_ids)
        r = rng.choice(rooms)
        offset_days = rng.uniform(-59.0, -0.2)
        day_base = (as_of + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_hour = rng.randint(9, 17)
        start_dt = day_base + timedelta(hours=start_hour)
        duration_hours = rng.choice([1, 2])
        end_dt = start_dt + timedelta(hours=duration_hours)
        created_dt = start_dt - timedelta(days=rng.randint(2, 7))

        reservations.append(
            SyntheticReservation(
                id=res_id,
                user_id=u_id,
                resource_type="room",
                seat_id=None,
                room_id=r.id,
                start_time=start_dt,
                end_time=end_dt,
                status="no_show",
                created_at=created_dt,
            )
        )
        res_id += 1

    return reservations
