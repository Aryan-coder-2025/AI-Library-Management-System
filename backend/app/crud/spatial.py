"""
CRUD module for Spatial Floor Plans, Resource Mapping & Wayfinding.
Provides efficient database queries and mutations for floors, layouts,
elements, spatial resource mappings, and wayfinding graphs.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    FloorPlanElementCreate,
    FloorPlanElementUpdate,
    FloorPlanUpdate,
    LibraryFloorCreate,
    LibraryFloorUpdate,
    SpatialResourceMappingCreate,
    SpatialResourceMappingUpdate,
)
from app.utils.date import get_utc_now


# ── Floor Operations ──────────────────────────────────────────────────────────

def get_floors(db: Session, include_inactive: bool = False) -> List[LibraryFloor]:
    """Retrieves all floors ordered by display_order and floor_number."""
    stmt = select(LibraryFloor)
    if not include_inactive:
        stmt = stmt.where(LibraryFloor.is_active.is_(True))
    stmt = stmt.order_by(LibraryFloor.display_order.asc(), LibraryFloor.floor_number.asc())
    return list(db.execute(stmt).scalars().all())


def get_floor_by_id(db: Session, floor_id: int) -> Optional[LibraryFloor]:
    return db.get(LibraryFloor, floor_id)


def get_floor_by_number(db: Session, floor_number: int) -> Optional[LibraryFloor]:
    stmt = select(LibraryFloor).where(LibraryFloor.floor_number == floor_number)
    return db.execute(stmt).scalars().first()


def create_floor(db: Session, floor_in: LibraryFloorCreate) -> LibraryFloor:
    floor = LibraryFloor(
        floor_number=floor_in.floor_number,
        name=floor_in.name,
        description=floor_in.description,
        display_order=floor_in.display_order,
        width=floor_in.width,
        height=floor_in.height,
        is_active=floor_in.is_active,
    )
    db.add(floor)
    db.flush()
    return floor


def update_floor(db: Session, floor: LibraryFloor, update_in: LibraryFloorUpdate) -> LibraryFloor:
    if update_in.name is not None:
        floor.name = update_in.name
    if update_in.description is not None:
        floor.description = update_in.description
    if update_in.display_order is not None:
        floor.display_order = update_in.display_order
    if update_in.width is not None:
        floor.width = update_in.width
    if update_in.height is not None:
        floor.height = update_in.height
    if update_in.is_active is not None:
        floor.is_active = update_in.is_active
    floor.updated_at = get_utc_now()
    db.flush()
    return floor


# ── FloorPlan Operations ──────────────────────────────────────────────────────

def get_layouts_by_floor(db: Session, floor_id: int) -> List[FloorPlan]:
    stmt = (
        select(FloorPlan)
        .where(FloorPlan.floor_id == floor_id)
        .order_by(FloorPlan.version.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_layout_by_id(db: Session, layout_id: int) -> Optional[FloorPlan]:
    return db.get(FloorPlan, layout_id)


def get_published_layout(db: Session, floor_id: int) -> Optional[FloorPlan]:
    floor = db.get(LibraryFloor, floor_id)
    if floor and floor.published_layout_id:
        return db.get(FloorPlan, floor.published_layout_id)
    stmt = (
        select(FloorPlan)
        .where(FloorPlan.floor_id == floor_id, FloorPlan.status == "published")
        .order_by(FloorPlan.version.desc())
    )
    return db.execute(stmt).scalars().first()


def create_layout(
    db: Session, floor_id: int, layout_in: FloorPlanCreate, user_id: Optional[int] = None
) -> FloorPlan:
    # Determine next version
    max_ver = db.execute(
        select(func.coalesce(func.max(FloorPlan.version), 0)).where(FloorPlan.floor_id == floor_id)
    ).scalar_one()

    layout = FloorPlan(
        floor_id=floor_id,
        version=max_ver + 1,
        status="draft",
        title=layout_in.title,
        description=layout_in.description,
        svg_viewbox=layout_in.svg_viewbox,
        created_by_user_id=user_id,
    )
    db.add(layout)
    db.flush()
    return layout


def update_layout(db: Session, layout: FloorPlan, update_in: FloorPlanUpdate) -> FloorPlan:
    if update_in.title is not None:
        layout.title = update_in.title
    if update_in.description is not None:
        layout.description = update_in.description
    if update_in.svg_viewbox is not None:
        layout.svg_viewbox = update_in.svg_viewbox
    layout.updated_at = get_utc_now()
    db.flush()
    return layout


def publish_layout(db: Session, layout: FloorPlan) -> FloorPlan:
    floor = db.get(LibraryFloor, layout.floor_id)
    now = get_utc_now()

    # Archive previous published layouts for this floor
    existing_published = (
        db.execute(
            select(FloorPlan).where(
                FloorPlan.floor_id == layout.floor_id,
                FloorPlan.status == "published",
                FloorPlan.id != layout.id,
            )
        )
        .scalars()
        .all()
    )
    for p in existing_published:
        p.status = "archived"
        p.updated_at = now

    layout.status = "published"
    layout.published_at = now
    layout.updated_at = now

    if floor:
        floor.published_layout_id = layout.id
        floor.updated_at = now

    db.flush()
    return layout


# ── FloorPlanElement Operations ───────────────────────────────────────────────

def get_elements_by_layout(db: Session, layout_id: int) -> List[FloorPlanElement]:
    stmt = (
        select(FloorPlanElement)
        .where(FloorPlanElement.layout_id == layout_id, FloorPlanElement.is_active.is_(True))
        .order_by(FloorPlanElement.display_order.asc(), FloorPlanElement.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_elements_by_floor(
    db: Session, floor_id: int, layout_id: Optional[int] = None
) -> List[FloorPlanElement]:
    stmt = select(FloorPlanElement).where(
        FloorPlanElement.floor_id == floor_id, FloorPlanElement.is_active.is_(True)
    )
    if layout_id is not None:
        stmt = stmt.where(FloorPlanElement.layout_id == layout_id)
    stmt = stmt.order_by(FloorPlanElement.display_order.asc(), FloorPlanElement.id.asc())
    return list(db.execute(stmt).scalars().all())


def get_element_by_id(db: Session, element_id: int) -> Optional[FloorPlanElement]:
    return db.get(FloorPlanElement, element_id)


def create_element(
    db: Session, floor_id: int, element_in: FloorPlanElementCreate
) -> FloorPlanElement:
    elem = FloorPlanElement(
        floor_id=floor_id,
        layout_id=element_in.layout_id,
        element_type=element_in.element_type,
        label=element_in.label,
        geometry_type=element_in.geometry_type,
        geometry_data=element_in.geometry_data,
        style_properties=element_in.style_properties,
        display_order=element_in.display_order,
        is_active=element_in.is_active,
    )
    db.add(elem)
    db.flush()
    return elem


def update_element(
    db: Session, element: FloorPlanElement, update_in: FloorPlanElementUpdate
) -> FloorPlanElement:
    if update_in.element_type is not None:
        element.element_type = update_in.element_type
    if update_in.label is not None:
        element.label = update_in.label
    if update_in.geometry_type is not None:
        element.geometry_type = update_in.geometry_type
    if update_in.geometry_data is not None:
        element.geometry_data = update_in.geometry_data
    if update_in.style_properties is not None:
        element.style_properties = update_in.style_properties
    if update_in.display_order is not None:
        element.display_order = update_in.display_order
    if update_in.is_active is not None:
        element.is_active = update_in.is_active
    element.updated_at = get_utc_now()
    db.flush()
    return element


def delete_element(db: Session, element: FloorPlanElement) -> None:
    db.delete(element)
    db.flush()


# ── SpatialResourceMapping Operations ─────────────────────────────────────────

def get_mappings_by_floor(db: Session, floor_id: int) -> List[SpatialResourceMapping]:
    stmt = (
        select(SpatialResourceMapping)
        .where(
            SpatialResourceMapping.floor_id == floor_id,
            SpatialResourceMapping.is_active.is_(True),
        )
        .order_by(SpatialResourceMapping.resource_type.asc(), SpatialResourceMapping.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_mapping_by_id(db: Session, mapping_id: int) -> Optional[SpatialResourceMapping]:
    return db.get(SpatialResourceMapping, mapping_id)


def get_mapping_by_resource(
    db: Session, resource_type: str, resource_id: int
) -> Optional[SpatialResourceMapping]:
    stmt = select(SpatialResourceMapping).where(
        SpatialResourceMapping.resource_type == resource_type,
        SpatialResourceMapping.resource_id == resource_id,
        SpatialResourceMapping.is_active.is_(True),
    )
    return db.execute(stmt).scalars().first()


def create_mapping(
    db: Session, floor_id: int, mapping_in: SpatialResourceMappingCreate
) -> SpatialResourceMapping:
    mapping = SpatialResourceMapping(
        floor_id=floor_id,
        resource_type=mapping_in.resource_type,
        resource_id=mapping_in.resource_id,
        label=mapping_in.label,
        x=mapping_in.x,
        y=mapping_in.y,
        width=mapping_in.width,
        height=mapping_in.height,
        rotation=mapping_in.rotation,
        is_active=mapping_in.is_active,
    )
    db.add(mapping)
    db.flush()
    return mapping


def update_mapping(
    db: Session, mapping: SpatialResourceMapping, update_in: SpatialResourceMappingUpdate
) -> SpatialResourceMapping:
    if update_in.label is not None:
        mapping.label = update_in.label
    if update_in.x is not None:
        mapping.x = update_in.x
    if update_in.y is not None:
        mapping.y = update_in.y
    if update_in.width is not None:
        mapping.width = update_in.width
    if update_in.height is not None:
        mapping.height = update_in.height
    if update_in.rotation is not None:
        mapping.rotation = update_in.rotation
    if update_in.is_active is not None:
        mapping.is_active = update_in.is_active
    mapping.updated_at = get_utc_now()
    db.flush()
    return mapping


def delete_mapping(db: Session, mapping: SpatialResourceMapping) -> None:
    db.delete(mapping)
    db.flush()


# ── Wayfinding Operations ─────────────────────────────────────────────────────

def get_nodes_by_floor(db: Session, floor_id: int) -> List[WayfindingNode]:
    stmt = (
        select(WayfindingNode)
        .where(WayfindingNode.floor_id == floor_id, WayfindingNode.is_active.is_(True))
    )
    return list(db.execute(stmt).scalars().all())


def get_all_wayfinding_nodes(db: Session) -> List[WayfindingNode]:
    stmt = select(WayfindingNode).where(WayfindingNode.is_active.is_(True))
    return list(db.execute(stmt).scalars().all())


def get_all_wayfinding_edges(db: Session) -> List[WayfindingEdge]:
    stmt = select(WayfindingEdge)
    return list(db.execute(stmt).scalars().all())


def find_node_for_resource(
    db: Session, resource_type: str, resource_id: int
) -> Optional[WayfindingNode]:
    stmt = select(WayfindingNode).where(
        WayfindingNode.resource_type == resource_type,
        WayfindingNode.resource_id == resource_id,
        WayfindingNode.is_active.is_(True),
    )
    return db.execute(stmt).scalars().first()


# ── Completeness Operations ───────────────────────────────────────────────────

def get_spatial_completeness(db: Session) -> Dict:
    """Computes mapped vs unmapped counts for zones, seats, and rooms across the library."""
    all_zones = db.execute(select(StudyZone.id)).scalars().all()
    all_seats = db.execute(select(StudySeat.id)).scalars().all()
    all_rooms = db.execute(select(StudyRoom.id)).scalars().all()

    mapped_zone_ids = set(
        db.execute(
            select(SpatialResourceMapping.resource_id).where(
                SpatialResourceMapping.resource_type == "zone",
                SpatialResourceMapping.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    mapped_seat_ids = set(
        db.execute(
            select(SpatialResourceMapping.resource_id).where(
                SpatialResourceMapping.resource_type == "seat",
                SpatialResourceMapping.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    mapped_room_ids = set(
        db.execute(
            select(SpatialResourceMapping.resource_id).where(
                SpatialResourceMapping.resource_type == "room",
                SpatialResourceMapping.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )

    unmapped_zones = [zid for zid in all_zones if zid not in mapped_zone_ids]
    unmapped_seats = [sid for sid in all_seats if sid not in mapped_seat_ids]
    unmapped_rooms = [rid for rid in all_rooms if rid not in mapped_room_ids]

    total_resources = len(all_zones) + len(all_seats) + len(all_rooms)
    total_mapped = len(mapped_zone_ids) + len(mapped_seat_ids) + len(mapped_room_ids)
    completeness_pct = (
        round((total_mapped / total_resources) * 100.0, 2) if total_resources > 0 else 100.0
    )

    pub_count = db.execute(
        select(func.count(LibraryFloor.id)).where(
            LibraryFloor.published_layout_id.is_not(None), LibraryFloor.is_active.is_(True)
        )
    ).scalar_one()

    draft_count = db.execute(
        select(func.count(FloorPlan.id)).where(FloorPlan.status == "draft")
    ).scalar_one()

    return {
        "total_zones": len(all_zones),
        "mapped_zones": len(mapped_zone_ids),
        "unmapped_zone_ids": unmapped_zones,
        "total_seats": len(all_seats),
        "mapped_seats": len(mapped_seat_ids),
        "unmapped_seat_ids": unmapped_seats,
        "total_rooms": len(all_rooms),
        "mapped_rooms": len(mapped_room_ids),
        "unmapped_room_ids": unmapped_rooms,
        "mapping_completeness_percentage": completeness_pct,
        "published_floors_count": int(pub_count or 0),
        "draft_floors_count": int(draft_count or 0),
    }

