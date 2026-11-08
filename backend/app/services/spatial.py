"""
Service module for Spatial Floor Plans, Resource Mapping & Wayfinding.
Handles business logic, real-time availability derivation, validation, publication,
batched resource lookups, and graph-based wayfinding algorithms.
"""
from collections import deque
from datetime import datetime, timezone
import heapq
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import spatial as crud_spatial
from app.models import (
    FloorPlan,
    FloorPlanElement,
    LibraryFloor,
    Reservation,
    SpatialResourceMapping,
    StudyRoom,
    StudySeat,
    StudyZone,
    WayfindingEdge,
    WayfindingNode,
)
from app.schemas import (
    FloorPlanCreate,
    FloorPlanDetailResponse,
    FloorPlanElementCreate,
    FloorPlanElementResponse,
    FloorPlanElementUpdate,
    FloorPlanResponse,
    FloorPlanUpdate,
    LibraryFloorCreate,
    LibraryFloorResponse,
    LibraryFloorUpdate,
    ResourceLocationResponse,
    SpatialCompletenessReport,
    SpatialResourceAvailability,
    SpatialResourceMappingCreate,
    SpatialResourceMappingResponse,
    SpatialResourceMappingUpdate,
    WayfindingRouteResponse,
    WayfindingStep,
)
from app.utils.date import get_utc_now


def _ensure_naive_utc(dt: datetime) -> datetime:
    """Normalizes datetime to naive UTC for consistent SQLite querying."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ── Floor Management Services ─────────────────────────────────────────────────

def get_all_floors_service(
    db: Session, include_inactive: bool = False
) -> List[LibraryFloorResponse]:
    floors = crud_spatial.get_floors(db=db, include_inactive=include_inactive)
    return [LibraryFloorResponse.model_validate(f) for f in floors]


def get_floor_service(db: Session, floor_id: int) -> LibraryFloorResponse:
    floor = crud_spatial.get_floor_by_id(db=db, floor_id=floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library floor ID {floor_id} not found.",
        )
    return LibraryFloorResponse.model_validate(floor)


def create_floor_service(db: Session, floor_in: LibraryFloorCreate) -> LibraryFloorResponse:
    existing = crud_spatial.get_floor_by_number(db=db, floor_number=floor_in.floor_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Floor number {floor_in.floor_number} already exists ('{existing.name}').",
        )
    floor = crud_spatial.create_floor(db=db, floor_in=floor_in)
    return LibraryFloorResponse.model_validate(floor)


def update_floor_service(
    db: Session, floor_id: int, update_in: LibraryFloorUpdate
) -> LibraryFloorResponse:
    floor = crud_spatial.get_floor_by_id(db=db, floor_id=floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library floor ID {floor_id} not found.",
        )
    updated = crud_spatial.update_floor(db=db, floor=floor, update_in=update_in)
    return LibraryFloorResponse.model_validate(updated)


# ── Floor Plan Detail & Availability Integration ──────────────────────────────

def get_floor_plan_detail_service(
    db: Session, floor_id: int, as_of: Optional[datetime] = None
) -> FloorPlanDetailResponse:
    """
    Returns full spatial floor-plan details including elements and mapped resources.
    Integrates real-time availability derived from active reservations without patron PII.
    Batches SQL queries to eliminate N+1 bottlenecks.
    """
    floor = crud_spatial.get_floor_by_id(db=db, floor_id=floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library floor ID {floor_id} not found.",
        )

    # 1. Resolve Layout (prefer published, fall back to latest draft)
    layout = crud_spatial.get_published_layout(db=db, floor_id=floor_id)
    if not layout:
        layouts = crud_spatial.get_layouts_by_floor(db=db, floor_id=floor_id)
        layout = layouts[0] if layouts else None

    # 2. Layout Elements
    elements = (
        crud_spatial.get_elements_by_layout(db=db, layout_id=layout.id)
        if layout
        else crud_spatial.get_elements_by_floor(db=db, floor_id=floor_id)
    )

    # 3. Spatial Resource Mappings
    mappings = crud_spatial.get_mappings_by_floor(db=db, floor_id=floor_id)

    # 4. Batched Real-Time Availability Derivation
    now = _ensure_naive_utc(as_of) if as_of is not None else _ensure_naive_utc(get_utc_now())

    # Active reservations currently underway
    res_stmt = select(Reservation).where(
        Reservation.status == "active",
        Reservation.start_time <= now,
        Reservation.end_time > now,
    )
    active_reservations = db.execute(res_stmt).scalars().all()

    seat_res_map: Dict[int, Reservation] = {}
    room_res_map: Dict[int, Reservation] = {}
    for r in active_reservations:
        if r.resource_type == "seat" and r.seat_id is not None:
            seat_res_map[r.seat_id] = r
        elif r.resource_type == "room" and r.room_id is not None:
            room_res_map[r.room_id] = r

    # Prefetch resource records
    seat_ids = [m.resource_id for m in mappings if m.resource_type == "seat"]
    room_ids = [m.resource_id for m in mappings if m.resource_type == "room"]
    zone_ids = [m.resource_id for m in mappings if m.resource_type == "zone"]

    seats_by_id = (
        {s.id: s for s in db.execute(select(StudySeat).where(StudySeat.id.in_(seat_ids))).scalars().all()}
        if seat_ids
        else {}
    )
    rooms_by_id = (
        {r.id: r for r in db.execute(select(StudyRoom).where(StudyRoom.id.in_(room_ids))).scalars().all()}
        if room_ids
        else {}
    )
    zones_by_id = (
        {z.id: z for z in db.execute(select(StudyZone).where(StudyZone.id.in_(zone_ids))).scalars().all()}
        if zone_ids
        else {}
    )

    # Zones for seat lookup
    all_zones = {z.id: z for z in db.execute(select(StudyZone)).scalars().all()}

    resources: List[SpatialResourceAvailability] = []
    for m in mappings:
        avail_status = "unknown"
        current_att = None
        cap = None
        zone_id = None
        zone_code = None
        zone_name = None
        details: Dict[str, Any] = {}

        if m.resource_type == "seat":
            seat = seats_by_id.get(m.resource_id)
            if seat:
                cap = 1
                zone = all_zones.get(seat.zone_id)
                if zone:
                    zone_id = zone.id
                    zone_code = zone.zone_code
                    zone_name = zone.name

                details = {
                    "seat_code": seat.seat_code,
                    "has_power_outlet": seat.has_power_outlet,
                    "has_monitor": seat.has_monitor,
                    "is_accessible": seat.is_accessible,
                }

                if not seat.is_active:
                    avail_status = "unavailable"
                else:
                    res = seat_res_map.get(seat.id)
                    if res is None:
                        avail_status = "available"
                    elif res.checked_in_at is not None:
                        avail_status = "occupied"
                        current_att = 1
                    else:
                        avail_status = "reserved"
                        current_att = 0

        elif m.resource_type == "room":
            room = rooms_by_id.get(m.resource_id)
            if room:
                cap = room.capacity
                details = {
                    "room_code": room.room_code,
                    "capacity": room.capacity,
                    "display_type": room.display_type,
                    "has_whiteboard": room.has_whiteboard,
                }

                if not room.is_active:
                    avail_status = "unavailable"
                else:
                    res = room_res_map.get(room.id)
                    if res is None:
                        avail_status = "available"
                    elif res.checked_in_at is not None:
                        avail_status = "occupied"
                        raw_att = (
                            res.actual_attendees
                            if res.actual_attendees is not None
                            else (res.expected_attendees or 1)
                        )
                        current_att = max(1, min(room.capacity, raw_att))
                    else:
                        avail_status = "reserved"
                        current_att = 0

        elif m.resource_type == "zone":
            zone = zones_by_id.get(m.resource_id)
            if zone:
                zone_id = zone.id
                zone_code = zone.zone_code
                zone_name = zone.name
                cap = zone.total_capacity
                details = {
                    "zone_code": zone.zone_code,
                    "noise_policy": zone.noise_policy,
                    "total_capacity": zone.total_capacity,
                }
                avail_status = "available" if zone.is_active else "unavailable"

        resources.append(
            SpatialResourceAvailability(
                resource_type=m.resource_type,
                resource_id=m.resource_id,
                label=m.label or f"{m.resource_type.capitalize()} #{m.resource_id}",
                availability_status=avail_status,
                current_attendees=current_att,
                capacity=cap,
                provenance="reservation_state",
                x=m.x,
                y=m.y,
                width=m.width,
                height=m.height,
                rotation=m.rotation,
                zone_id=zone_id,
                zone_code=zone_code,
                zone_name=zone_name,
                details=details,
            )
        )

    return FloorPlanDetailResponse(
        floor=LibraryFloorResponse.model_validate(floor),
        layout=FloorPlanResponse.model_validate(layout) if layout else None,
        elements=[FloorPlanElementResponse.model_validate(e) for e in elements],
        resources=resources,
        is_demonstration_layout=True,
        disclosure="ILLUSTRATIVE DEMONSTRATION LAYOUT — NOT A SURVEYED BUILDING PLAN",
    )


# ── Layout Management Services ────────────────────────────────────────────────

def get_layouts_service(db: Session, floor_id: int) -> List[FloorPlanResponse]:
    floor = crud_spatial.get_floor_by_id(db=db, floor_id=floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library floor ID {floor_id} not found.",
        )
    layouts = crud_spatial.get_layouts_by_floor(db=db, floor_id=floor_id)
    return [FloorPlanResponse.model_validate(l) for l in layouts]


def create_layout_service(
    db: Session, floor_id: int, layout_in: FloorPlanCreate, user_id: Optional[int] = None
) -> FloorPlanResponse:
    floor = crud_spatial.get_floor_by_id(db=db, floor_id=floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library floor ID {floor_id} not found.",
        )
    layout = crud_spatial.create_layout(db=db, floor_id=floor_id, layout_in=layout_in, user_id=user_id)
    return FloorPlanResponse.model_validate(layout)


def update_layout_service(
    db: Session, layout_id: int, update_in: FloorPlanUpdate
) -> FloorPlanResponse:
    layout = crud_spatial.get_layout_by_id(db=db, layout_id=layout_id)
    if not layout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor plan ID {layout_id} not found.",
        )
    updated = crud_spatial.update_layout(db=db, layout=layout, update_in=update_in)
    return FloorPlanResponse.model_validate(updated)


def validate_layout_service(db: Session, layout_id: int) -> Dict[str, Any]:
    """
    Validates layout integrity prior to publication:
    - Floor exists and is active.
    - All mapped resources exist in the database.
    - Mapped resources match the floor number.
    - Normalized coordinates reside in [0.0, 1.05].
    - No duplicate mappings exist.
    """
    layout = crud_spatial.get_layout_by_id(db=db, layout_id=layout_id)
    if not layout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor plan ID {layout_id} not found.",
        )

    floor = crud_spatial.get_floor_by_id(db=db, floor_id=layout.floor_id)
    if not floor or not floor.is_active:
        return {"is_valid": False, "errors": ["Floor is missing or inactive."], "warnings": []}

    errors: List[str] = []
    warnings: List[str] = []

    mappings = crud_spatial.get_mappings_by_floor(db=db, floor_id=floor.id)
    seen_resources: Set[Tuple[str, int]] = set()

    all_zones = {z.id: z for z in db.execute(select(StudyZone)).scalars().all()}
    all_seats = {s.id: s for s in db.execute(select(StudySeat)).scalars().all()}
    all_rooms = {r.id: r for r in db.execute(select(StudyRoom)).scalars().all()}

    for m in mappings:
        pair = (m.resource_type, m.resource_id)
        if pair in seen_resources:
            errors.append(f"Duplicate mapping detected for {m.resource_type} ID {m.resource_id}.")
        seen_resources.add(pair)

        if not (0.0 <= m.x <= 1.05) or not (0.0 <= m.y <= 1.05):
            errors.append(
                f"Coordinates ({m.x:.2f}, {m.y:.2f}) for {m.resource_type} #{m.resource_id} outside bounds [0.0, 1.05]."
            )

        if m.resource_type == "seat":
            seat = all_seats.get(m.resource_id)
            if not seat:
                errors.append(f"Referenced seat ID {m.resource_id} does not exist.")
            elif not seat.is_active:
                warnings.append(f"Seat '{seat.seat_code}' (ID {seat.id}) is inactive/decommissioned.")
            else:
                zone = all_zones.get(seat.zone_id)
                if zone and zone.floor != floor.floor_number:
                    errors.append(
                        f"Seat '{seat.seat_code}' belongs to zone floor {zone.floor}, but mapped to floor {floor.floor_number}."
                    )
        elif m.resource_type == "room":
            room = all_rooms.get(m.resource_id)
            if not room:
                errors.append(f"Referenced room ID {m.resource_id} does not exist.")
            elif not room.is_active:
                warnings.append(f"Room '{room.room_code}' (ID {room.id}) is inactive/decommissioned.")
        elif m.resource_type == "zone":
            zone = all_zones.get(m.resource_id)
            if not zone:
                errors.append(f"Referenced zone ID {m.resource_id} does not exist.")
            elif not zone.is_active:
                warnings.append(f"Zone '{zone.zone_code}' (ID {zone.id}) is inactive/decommissioned.")
            elif zone.floor != floor.floor_number:
                errors.append(
                    f"Zone '{zone.zone_code}' is configured for floor {zone.floor}, but mapped to floor {floor.floor_number}."
                )

    if not mappings:
        warnings.append("Layout contains zero mapped resources.")

    elements = crud_spatial.get_elements_by_layout(db=db, layout_id=layout.id)
    if not elements:
        warnings.append("Layout contains zero structural elements.")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "mapped_resources_count": len(mappings),
        "elements_count": len(elements),
    }


def publish_layout_service(db: Session, layout_id: int) -> FloorPlanResponse:
    """Validates and publishes a floor plan draft."""
    val = validate_layout_service(db=db, layout_id=layout_id)
    if not val["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Cannot publish layout due to validation errors.",
                "errors": val["errors"],
            },
        )

    layout = crud_spatial.get_layout_by_id(db=db, layout_id=layout_id)
    published = crud_spatial.publish_layout(db=db, layout=layout)
    return FloorPlanResponse.model_validate(published)


# ── Floor Plan Elements Services ──────────────────────────────────────────────

def create_element_service(
    db: Session, floor_id: int, element_in: FloorPlanElementCreate
) -> FloorPlanElementResponse:
    floor = crud_spatial.get_floor_by_id(db=db, floor_id=floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library floor ID {floor_id} not found.",
        )
    elem = crud_spatial.create_element(db=db, floor_id=floor_id, element_in=element_in)
    return FloorPlanElementResponse.model_validate(elem)


def update_element_service(
    db: Session, element_id: int, update_in: FloorPlanElementUpdate
) -> FloorPlanElementResponse:
    elem = crud_spatial.get_element_by_id(db=db, element_id=element_id)
    if not elem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor plan element ID {element_id} not found.",
        )
    updated = crud_spatial.update_element(db=db, element=elem, update_in=update_in)
    return FloorPlanElementResponse.model_validate(updated)


def delete_element_service(db: Session, element_id: int) -> Dict[str, str]:
    elem = crud_spatial.get_element_by_id(db=db, element_id=element_id)
    if not elem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor plan element ID {element_id} not found.",
        )
    crud_spatial.delete_element(db=db, element=elem)
    return {"message": f"Element {element_id} deleted."}


# ── Spatial Resource Mapping Services ─────────────────────────────────────────

def create_resource_mapping_service(
    db: Session, floor_id: int, mapping_in: SpatialResourceMappingCreate
) -> SpatialResourceMappingResponse:
    floor = crud_spatial.get_floor_by_id(db=db, floor_id=floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library floor ID {floor_id} not found.",
        )

    # Referential verification
    if mapping_in.resource_type == "seat":
        seat = db.get(StudySeat, mapping_in.resource_id)
        if not seat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"StudySeat ID {mapping_in.resource_id} not found.",
            )
        zone = db.get(StudyZone, seat.zone_id)
        if zone and zone.floor != floor.floor_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Seat '{seat.seat_code}' belongs to zone floor {zone.floor}, incompatible with floor {floor.floor_number}.",
            )
    elif mapping_in.resource_type == "room":
        room = db.get(StudyRoom, mapping_in.resource_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"StudyRoom ID {mapping_in.resource_id} not found.",
            )
    elif mapping_in.resource_type == "zone":
        zone = db.get(StudyZone, mapping_in.resource_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"StudyZone ID {mapping_in.resource_id} not found.",
            )
        if zone.floor != floor.floor_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Zone '{zone.zone_code}' is on floor {zone.floor}, incompatible with floor {floor.floor_number}.",
            )

    # Check for existing mapping
    existing = crud_spatial.get_mapping_by_resource(
        db=db, resource_type=mapping_in.resource_type, resource_id=mapping_in.resource_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{mapping_in.resource_type.capitalize()} ID {mapping_in.resource_id} is already mapped on floor ID {existing.floor_id}.",
        )

    mapping = crud_spatial.create_mapping(db=db, floor_id=floor_id, mapping_in=mapping_in)
    return SpatialResourceMappingResponse.model_validate(mapping)


def update_resource_mapping_service(
    db: Session, mapping_id: int, update_in: SpatialResourceMappingUpdate
) -> SpatialResourceMappingResponse:
    mapping = crud_spatial.get_mapping_by_id(db=db, mapping_id=mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spatial mapping ID {mapping_id} not found.",
        )
    updated = crud_spatial.update_mapping(db=db, mapping=mapping, update_in=update_in)
    return SpatialResourceMappingResponse.model_validate(updated)


def delete_resource_mapping_service(db: Session, mapping_id: int) -> Dict[str, str]:
    mapping = crud_spatial.get_mapping_by_id(db=db, mapping_id=mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spatial mapping ID {mapping_id} not found.",
        )
    crud_spatial.delete_mapping(db=db, mapping=mapping)
    return {"message": f"Mapping {mapping_id} deleted."}


# ── Spatial Lookup & Wayfinding Services ───────────────────────────────────────

def get_resource_location_service(
    db: Session, resource_type: str, resource_id: int
) -> ResourceLocationResponse:
    """Finds the spatial coordinates, floor, zone, and availability of any library resource."""
    if resource_type not in ("seat", "room", "zone"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="resource_type must be 'seat', 'room', or 'zone'.",
        )

    mapping = crud_spatial.get_mapping_by_resource(
        db=db, resource_type=resource_type, resource_id=resource_id
    )
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type.capitalize()} ID {resource_id} is not mapped to any floor plan.",
        )

    floor = crud_spatial.get_floor_by_id(db=db, floor_id=mapping.floor_id)
    floor_name = floor.name if floor else f"Floor {mapping.floor_id}"
    floor_num = floor.floor_number if floor else 0

    zone_id = None
    zone_code = None
    zone_name = None
    avail_status = "available"
    guidance = f"Located on {floor_name}."

    if resource_type == "seat":
        seat = db.get(StudySeat, resource_id)
        if seat:
            zone = db.get(StudyZone, seat.zone_id)
            if zone:
                zone_id = zone.id
                zone_code = zone.zone_code
                zone_name = zone.name
                guidance = f"Proceed to {floor_name}, enter {zone.name} ({zone.noise_policy} policy). Seat '{seat.seat_code}' is situated at coordinates ({mapping.x:.2f}, {mapping.y:.2f})."
    elif resource_type == "room":
        room = db.get(StudyRoom, resource_id)
        if room:
            guidance = f"Proceed to {floor_name}. Study Room '{room.room_code} - {room.name}' (capacity: {room.capacity}) is at coordinates ({mapping.x:.2f}, {mapping.y:.2f})."
    elif resource_type == "zone":
        zone = db.get(StudyZone, resource_id)
        if zone:
            zone_id = zone.id
            zone_code = zone.zone_code
            zone_name = zone.name
            guidance = f"{zone.name} spans the {floor_name} floor plan."

    return ResourceLocationResponse(
        resource_type=resource_type,
        resource_id=resource_id,
        label=mapping.label,
        floor_id=mapping.floor_id,
        floor_number=floor_num,
        floor_name=floor_name,
        zone_id=zone_id,
        zone_code=zone_code,
        zone_name=zone_name,
        x=mapping.x,
        y=mapping.y,
        availability_status=avail_status,
        directional_guidance=guidance,
        is_demonstration=True,
        disclosure="ILLUSTRATIVE DEMONSTRATION LAYOUT — NOT A SURVEYED BUILDING PLAN",
    )


def calculate_wayfinding_route_service(
    db: Session,
    resource_type: str,
    resource_id: int,
    from_node_id: Optional[int] = None,
) -> WayfindingRouteResponse:
    """
    Computes shortest-path wayfinding from an entrance or specified node to the target resource.
    Utilizes Dijkstra/BFS graph traversal across wayfinding nodes and edges.
    """
    mapping = crud_spatial.get_mapping_by_resource(
        db=db, resource_type=resource_type, resource_id=resource_id
    )
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type.capitalize()} ID {resource_id} is not mapped to any floor plan.",
        )

    floor = crud_spatial.get_floor_by_id(db=db, floor_id=mapping.floor_id)
    floor_num = floor.floor_number if floor else 0

    # Retrieve all nodes and edges
    all_nodes = crud_spatial.get_all_wayfinding_nodes(db=db)
    all_edges = crud_spatial.get_all_wayfinding_edges(db=db)

    nodes_by_id = {n.id: n for n in all_nodes}

    # Locate destination node: exact resource node or closest node on destination floor
    target_node = crud_spatial.find_node_for_resource(
        db=db, resource_type=resource_type, resource_id=resource_id
    )
    if not target_node:
        # Find closest node on destination floor
        floor_nodes = [n for n in all_nodes if n.floor_id == mapping.floor_id]
        if floor_nodes:
            target_node = min(
                floor_nodes,
                key=lambda n: (n.x - mapping.x) ** 2 + (n.y - mapping.y) ** 2,
            )

    # Locate start node: from_node_id or default entrance on destination floor
    start_node = None
    if from_node_id is not None:
        start_node = nodes_by_id.get(from_node_id)
    if not start_node:
        entrances = [
            n
            for n in all_nodes
            if n.floor_id == mapping.floor_id and n.node_type in ("entrance", "hallway")
        ]
        start_node = entrances[0] if entrances else target_node

    # If no wayfinding graph exists for this floor, provide direct geometric line
    if not target_node or not start_node or not all_edges:
        dest_x = mapping.x
        dest_y = mapping.y
        path_points = [[0.1, 0.9], [dest_x, dest_y]]
        steps = [
            WayfindingStep(
                step_number=1,
                instruction=f"Enter {floor.name if floor else 'library floor'}.",
                floor_number=floor_num,
                node_type="entrance",
                x=0.1,
                y=0.9,
            ),
            WayfindingStep(
                step_number=2,
                instruction=f"Proceed directly to {mapping.label or resource_type}.",
                floor_number=floor_num,
                node_type="destination",
                x=dest_x,
                y=dest_y,
            ),
        ]
        return WayfindingRouteResponse(
            destination_resource_type=resource_type,
            destination_resource_id=resource_id,
            destination_label=mapping.label or f"{resource_type.capitalize()} #{resource_id}",
            destination_floor_number=floor_num,
            total_distance=1.0,
            is_accessible=True,
            path_points=path_points,
            steps=steps,
            is_demonstration=True,
            disclosure="ILLUSTRATIVE DEMONSTRATION ROUTE — SINGLE-FLOOR WAYFINDING ONLY; ELEVATOR ACCESSIBILITY REQUIRES DESTINATION-FLOOR ENTRANCE",
        )

    # Dijkstra shortest path search
    adj: Dict[int, List[Tuple[int, float, bool]]] = {n.id: [] for n in all_nodes}
    for e in all_edges:
        adj[e.from_node_id].append((e.to_node_id, e.distance, e.is_accessible))
        # Bidirectional graph for walkways
        adj[e.to_node_id].append((e.from_node_id, e.distance, e.is_accessible))

    dist: Dict[int, float] = {n.id: float("inf") for n in all_nodes}
    prev: Dict[int, Optional[int]] = {n.id: None for n in all_nodes}
    dist[start_node.id] = 0.0

    pq = [(0.0, start_node.id)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == target_node.id:
            break
        for v, weight, is_acc in adj.get(u, []):
            if dist[u] + weight < dist[v]:
                dist[v] = dist[u] + weight
                prev[v] = u
                heapq.heappush(pq, (dist[v], v))

    # Reconstruct path
    curr = target_node.id
    path_nodes: List[WayfindingNode] = []
    if dist[target_node.id] != float("inf"):
        while curr is not None:
            path_nodes.append(nodes_by_id[curr])
            curr = prev[curr]
        path_nodes.reverse()
    else:
        path_nodes = [start_node, target_node]

    path_points = [[n.x, n.y] for n in path_nodes]
    # Ensure final point reaches exact mapped resource coordinates
    if path_points[-1] != [mapping.x, mapping.y]:
        path_points.append([mapping.x, mapping.y])

    steps: List[WayfindingStep] = []
    for idx, n in enumerate(path_nodes):
        inst = f"Pass {n.label or n.node_type}."
        if idx == 0:
            inst = f"Start at {n.label or 'entrance'}."
        elif idx == len(path_nodes) - 1:
            inst = f"Arrive at {mapping.label or resource_type}."
        steps.append(
            WayfindingStep(
                step_number=idx + 1,
                instruction=inst,
                floor_number=floor_num,
                node_type=n.node_type,
                x=n.x,
                y=n.y,
            )
        )

    return WayfindingRouteResponse(
        destination_resource_type=resource_type,
        destination_resource_id=resource_id,
        destination_label=mapping.label or f"{resource_type.capitalize()} #{resource_id}",
        destination_floor_number=floor_num,
        total_distance=round(dist[target_node.id], 2) if dist[target_node.id] != float("inf") else 1.0,
        is_accessible=True,
        path_points=path_points,
        steps=steps,
        is_demonstration=True,
        disclosure="ILLUSTRATIVE DEMONSTRATION ROUTE — SINGLE-FLOOR WAYFINDING ONLY; CROSS-FLOOR TRANSIT USES DESTINATION-FLOOR CORE",
    )


# ── Completeness Report Service ───────────────────────────────────────────────

def get_spatial_completeness_report_service(db: Session) -> SpatialCompletenessReport:
    raw = crud_spatial.get_spatial_completeness(db=db)
    return SpatialCompletenessReport(**raw)

