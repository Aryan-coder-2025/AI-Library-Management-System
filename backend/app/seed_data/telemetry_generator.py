"""Deterministic synthetic telemetry generator for AI Library Management System.

Generates:
- 20,000 Occupancy Observations across 8 Study Zones
- 15,000 Search Events
- 6,000 Inventory Audit Events
Total = 41,000 telemetry events.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional

from app.seed_data.generator import SeederConfig, get_namespace_rng
from app.seed_data.vocabulary import SEARCH_SAMPLE_QUERIES, INVENTORY_NOTES
from app.seed_data.users_generator import SyntheticUser
from app.seed_data.spaces_generator import SyntheticStudyZone
from app.seed_data.catalogue_generator import SyntheticBook, SyntheticBookCopy

logger = logging.getLogger(__name__)


@dataclass
class SyntheticOccupancyObservation:
    id: int
    zone_id: int
    recorded_at: datetime
    observed_count: int
    capacity_utilization: float
    source_sensor_id: str


@dataclass
class SyntheticSearchEvent:
    id: int
    user_id: Optional[int]
    query_text: str
    search_type: str
    results_count: int
    latency_ms: float
    executed_at: datetime


@dataclass
class SyntheticInventoryEvent:
    id: int
    copy_id: int
    auditor_id: int
    event_type: str
    notes: Optional[str]
    recorded_at: datetime


def generate_telemetry(
    config: SeederConfig,
    users: List[SyntheticUser],
    zones: List[SyntheticStudyZone],
    copies: List[SyntheticBookCopy],
) -> Dict[str, List]:
    """
    Generates:
    - 20,000 Occupancy Observations
    - 15,000 Search Events
    - 6,000 Inventory Events
    """
    rng = get_namespace_rng(config.base_seed, "telemetry")
    as_of = config.as_of

    librarian_ids = [u.id for u in users if u.role == "librarian"]
    borrower_ids = [u.id for u in users if u.role in ("student", "teacher")]

    # ── 1. 20,000 Occupancy Observations ──────────────────────────────────────
    # 104 days x 24 hours x 8 zones = 19,968 regular hourly readings
    # + 32 high-resolution exam week spot readings = 20,000 exact readings
    occupancy_obs: List[SyntheticOccupancyObservation] = []
    obs_id = 1

    sensor_ids = {
        z.id: f"SENSOR-{z.zone_code.replace('ZONE-', '')}-01" for z in zones
    }

    # 104 days prior to as_of
    start_date = (as_of - timedelta(days=104)).replace(hour=0, minute=0, second=0, microsecond=0)
    for day_offset in range(104):
        curr_day = start_date + timedelta(days=day_offset)
        is_weekend = (curr_day.weekday() >= 5)

        for hour in range(24):
            recorded_dt = curr_day + timedelta(hours=hour)
            
            # Diurnal occupancy pattern
            if 0 <= hour < 7:
                base_factor = 0.05
            elif 7 <= hour < 10:
                base_factor = 0.35
            elif 10 <= hour < 17:
                base_factor = 0.80 if not is_weekend else 0.50
            elif 17 <= hour < 22:
                base_factor = 0.65
            else:
                base_factor = 0.20

            for zone in zones:
                jitter = rng.uniform(-0.15, 0.15)
                util = max(0.0, min(1.0, base_factor + jitter))
                count = int(round(util * zone.total_capacity))
                actual_util = round(count / zone.total_capacity, 4)

                occupancy_obs.append(
                    SyntheticOccupancyObservation(
                        id=obs_id,
                        zone_id=zone.id,
                        recorded_at=recorded_dt,
                        observed_count=count,
                        capacity_utilization=actual_util,
                        source_sensor_id=sensor_ids[zone.id],
                    )
                )
                obs_id += 1

    # Remaining 32 spot audit readings to hit exactly 20,000
    for _ in range(32):
        zone = rng.choice(zones)
        spot_dt = as_of - timedelta(days=rng.randint(1, 14), hours=rng.randint(8, 20), minutes=rng.randint(1, 59))
        util = rng.uniform(0.60, 0.95)
        count = int(round(util * zone.total_capacity))
        actual_util = round(count / zone.total_capacity, 4)

        occupancy_obs.append(
            SyntheticOccupancyObservation(
                id=obs_id,
                zone_id=zone.id,
                recorded_at=spot_dt,
                observed_count=count,
                capacity_utilization=actual_util,
                source_sensor_id=sensor_ids[zone.id],
            )
        )
        obs_id += 1

    # ── 2. 15,000 Search Events ───────────────────────────────────────────────
    search_events: List[SyntheticSearchEvent] = []
    search_types = ["text", "semantic", "category"]
    type_weights = [0.55, 0.35, 0.10]

    for s_id in range(1, 15001):
        # 85% authenticated, 15% anonymous
        user_id = rng.choice(borrower_ids) if rng.random() < 0.85 else None
        query = rng.choice(SEARCH_SAMPLE_QUERIES)
        stype = rng.choices(search_types, weights=type_weights, k=1)[0]
        
        # Latency and results count
        if stype == "semantic":
            latency = round(rng.uniform(45.0, 180.0), 2)
            results = rng.randint(3, 20)
        elif stype == "text":
            latency = round(rng.uniform(8.0, 45.0), 2)
            results = rng.randint(1, 35)
        else:
            latency = round(rng.uniform(5.0, 25.0), 2)
            results = rng.randint(5, 50)

        # Spread over last 90 days
        exec_dt = as_of - timedelta(seconds=rng.randint(0, 90 * 86400))

        search_events.append(
            SyntheticSearchEvent(
                id=s_id,
                user_id=user_id,
                query_text=query,
                search_type=stype,
                results_count=results,
                latency_ms=latency,
                executed_at=exec_dt,
            )
        )

    # ── 3. 6,000 Inventory Events ─────────────────────────────────────────────
    inventory_events: List[SyntheticInventoryEvent] = []
    event_types = ["audit", "rfid_scan", "condition_check", "maintenance", "relocation"]
    event_weights = [0.50, 0.25, 0.15, 0.06, 0.04]

    for inv_id in range(1, 6001):
        copy = rng.choice(copies)
        auditor_id = rng.choice(librarian_ids)
        etype = rng.choices(event_types, weights=event_weights, k=1)[0]
        notes = rng.choice(INVENTORY_NOTES)
        # Event happened after copy acquisition
        time_span = (as_of - copy.acquisition_date).total_seconds()
        offset = rng.randint(0, max(1, int(time_span)))
        rec_dt = copy.acquisition_date + timedelta(seconds=offset)

        inventory_events.append(
            SyntheticInventoryEvent(
                id=inv_id,
                copy_id=copy.id,
                auditor_id=auditor_id,
                event_type=etype,
                notes=notes,
                recorded_at=rec_dt,
            )
        )

    return {
        "occupancy_observations": occupancy_obs,
        "search_events": search_events,
        "inventory_events": inventory_events,
    }

