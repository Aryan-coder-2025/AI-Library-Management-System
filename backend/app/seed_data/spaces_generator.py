"""Deterministic synthetic space generator for AI Library Management System.

Generates:
- 8 Study Zones
- 150 Study Seats
- 10 Study Rooms
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.seed_data.generator import SeederConfig, get_namespace_rng
from app.seed_data.vocabulary import ZONE_DEFINITIONS, ROOM_DEFINITIONS


@dataclass
class SyntheticStudyZone:
    id: int
    zone_code: str
    name: str
    floor: int
    total_capacity: int
    noise_policy: str
    is_active: bool
    created_at: datetime


@dataclass
class SyntheticStudySeat:
    id: int
    zone_id: int
    seat_code: str
    has_power_outlet: bool
    has_monitor: bool
    is_accessible: bool
    is_active: bool
    created_at: datetime


@dataclass
class SyntheticStudyRoom:
    id: int
    room_code: str
    name: str
    capacity: int
    display_type: Optional[str]
    has_whiteboard: bool
    is_active: bool
    created_at: datetime


def generate_spaces(config: SeederConfig) -> Dict[str, List]:
    """
    Generates:
    - 8 Zones
    - 150 Seats (distributed across the 8 zones matching zone capacity)
    - 10 Rooms
    """
    rng = get_namespace_rng(config.base_seed, "spaces")
    base_created = config.as_of - timedelta(days=365)

    zones: List[SyntheticStudyZone] = []
    seats: List[SyntheticStudySeat] = []
    rooms: List[SyntheticStudyRoom] = []

    # ── 1. 8 Study Zones ──────────────────────────────────────────────────────
    for idx, z_def in enumerate(ZONE_DEFINITIONS, start=1):
        zones.append(
            SyntheticStudyZone(
                id=idx,
                zone_code=z_def["zone_code"],
                name=z_def["name"],
                floor=z_def["floor"],
                total_capacity=z_def["capacity"],
                noise_policy=z_def["policy"],
                is_active=True,
                created_at=base_created,
            )
        )

    # ── 2. 150 Study Seats ────────────────────────────────────────────────────
    seat_id = 1
    zone_prefix_map = {
        "ZONE-G-SILENT": "G-S",
        "ZONE-1-COLLAB": "1-C",
        "ZONE-1-QUIET": "1-Q",
        "ZONE-2-TECH": "2-T",
        "ZONE-2-GRAD": "2-G",
        "ZONE-3-SILENT": "3-S",
        "ZONE-3-MEDIA": "3-M",
        "ZONE-3-MATH": "3-A",
    }

    for zone in zones:
        prefix = zone_prefix_map.get(zone.zone_code, f"Z{zone.id}")
        for s_idx in range(1, zone.total_capacity + 1):
            code = f"SEAT-{prefix}-{s_idx:02d}"
            # Distribution: 80% power, 30% monitor, 15% wheelchair accessible
            has_power = rng.random() < 0.80
            has_monitor = rng.random() < 0.30
            is_accessible = rng.random() < 0.15
            seats.append(
                SyntheticStudySeat(
                    id=seat_id,
                    zone_id=zone.id,
                    seat_code=code,
                    has_power_outlet=has_power,
                    has_monitor=has_monitor,
                    is_accessible=is_accessible,
                    is_active=True,
                    created_at=base_created,
                )
            )
            seat_id += 1

    # ── 3. 10 Study Rooms ─────────────────────────────────────────────────────
    for idx, r_def in enumerate(ROOM_DEFINITIONS, start=1):
        rooms.append(
            SyntheticStudyRoom(
                id=idx,
                room_code=r_def["room_code"],
                name=r_def["name"],
                capacity=r_def["capacity"],
                display_type=r_def["display"],
                has_whiteboard=r_def["whiteboard"],
                is_active=True,
                created_at=base_created,
            )
        )

    return {
        "zones": zones,
        "seats": seats,
        "rooms": rooms,
    }

