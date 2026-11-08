"""
API router for Interactive Floor Plans, Spatial Resource Mapping & Wayfinding.
Provides public discovery endpoints for floor plans and wayfinding routes,
and staff-only endpoints for spatial management, drafts, and layout publication.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user, require_role
from app.models import User
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
    SpatialResourceMappingCreate,
    SpatialResourceMappingResponse,
    SpatialResourceMappingUpdate,
    WayfindingRouteResponse,
)
from app.services import spatial as spatial_service

router = APIRouter(prefix="/api/spaces", tags=["Spatial Floor Plans & Wayfinding"])


# ── Public / Student Discovery Endpoints ──────────────────────────────────────

@router.get("/floors", response_model=List[LibraryFloorResponse])
def get_floors(
    include_inactive: bool = Query(False, description="Include inactive floors (staff only)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieves all library floors."""
    if include_inactive and current_user.role not in ("librarian", "admin"):
        include_inactive = False
    return spatial_service.get_all_floors_service(db=db, include_inactive=include_inactive)


@router.get("/floors/{floor_id}", response_model=LibraryFloorResponse)
def get_floor(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieves a single library floor by ID."""
    return spatial_service.get_floor_service(db=db, floor_id=floor_id)


@router.get("/floors/{floor_id}/detail", response_model=FloorPlanDetailResponse)
def get_floor_plan_detail(
    floor_id: int,
    as_of: Optional[datetime] = Query(None, description="Optional timestamp for availability evaluation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves complete interactive floor-plan layout for the specified floor,
    including architectural SVG elements, zone boundaries, and real-time resource availability.
    """
    return spatial_service.get_floor_plan_detail_service(
        db=db, floor_id=floor_id, as_of=as_of
    )


@router.get(
    "/resources/{resource_type}/{resource_id}/location",
    response_model=ResourceLocationResponse,
)
def get_resource_location(
    resource_type: str,
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Locates any library resource (seat, room, zone) spatially.
    Returns floor, zone, coordinates, availability, and directional guidance.
    """
    return spatial_service.get_resource_location_service(
        db=db, resource_type=resource_type, resource_id=resource_id
    )


@router.get(
    "/resources/{resource_type}/{resource_id}/route",
    response_model=WayfindingRouteResponse,
)
def get_wayfinding_route(
    resource_type: str,
    resource_id: int,
    from_node_id: Optional[int] = Query(None, description="Optional origin wayfinding node ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Computes shortest-path wayfinding from an entrance or specified node to the destination resource.
    Provides path coordinates and step-by-step turn guidance.
    """
    return spatial_service.calculate_wayfinding_route_service(
        db=db,
        resource_type=resource_type,
        resource_id=resource_id,
        from_node_id=from_node_id,
    )


# ── Staff Management Endpoints (Librarian & Admin) ───────────────────────────

@router.post("/floors", response_model=LibraryFloorResponse, status_code=status.HTTP_201_CREATED)
def create_floor(
    floor_in: LibraryFloorCreate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Creates a new library floor."""
    return spatial_service.create_floor_service(db=db, floor_in=floor_in)


@router.patch("/floors/{floor_id}", response_model=LibraryFloorResponse)
def update_floor(
    floor_id: int,
    update_in: LibraryFloorUpdate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Updates library floor configuration."""
    return spatial_service.update_floor_service(db=db, floor_id=floor_id, update_in=update_in)


@router.get("/floors/{floor_id}/layouts", response_model=List[FloorPlanResponse])
def get_floor_layouts(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Lists all layout revisions (drafts, published, archived) for a floor."""
    return spatial_service.get_layouts_service(db=db, floor_id=floor_id)


@router.post(
    "/floors/{floor_id}/layouts",
    response_model=FloorPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_floor_layout(
    floor_id: int,
    layout_in: FloorPlanCreate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Creates a new draft layout revision for a floor."""
    return spatial_service.create_layout_service(
        db=db, floor_id=floor_id, layout_in=layout_in, user_id=current_user.id
    )


@router.patch("/layouts/{layout_id}", response_model=FloorPlanResponse)
def update_layout(
    layout_id: int,
    update_in: FloorPlanUpdate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Updates draft layout metadata."""
    return spatial_service.update_layout_service(
        db=db, layout_id=layout_id, update_in=update_in
    )


@router.post("/layouts/{layout_id}/validate")
def validate_layout(
    layout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Validates layout draft integrity prior to publication."""
    return spatial_service.validate_layout_service(db=db, layout_id=layout_id)


@router.post("/layouts/{layout_id}/publish", response_model=FloorPlanResponse)
def publish_layout(
    layout_id: int,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Validates and publishes a floor plan draft as the authoritative layout."""
    return spatial_service.publish_layout_service(db=db, layout_id=layout_id)


@router.post(
    "/floors/{floor_id}/elements",
    response_model=FloorPlanElementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_layout_element(
    floor_id: int,
    element_in: FloorPlanElementCreate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Adds a visual/structural element to a floor plan."""
    return spatial_service.create_element_service(
        db=db, floor_id=floor_id, element_in=element_in
    )


@router.patch("/layout-elements/{element_id}", response_model=FloorPlanElementResponse)
def update_layout_element(
    element_id: int,
    update_in: FloorPlanElementUpdate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Updates a structural element's geometry or styling."""
    return spatial_service.update_element_service(
        db=db, element_id=element_id, update_in=update_in
    )


@router.delete("/layout-elements/{element_id}")
def delete_layout_element(
    element_id: int,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Removes a structural element from a floor plan."""
    return spatial_service.delete_element_service(db=db, element_id=element_id)


@router.post(
    "/floors/{floor_id}/mappings",
    response_model=SpatialResourceMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource_mapping(
    floor_id: int,
    mapping_in: SpatialResourceMappingCreate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Maps an existing seat, room, or zone to spatial coordinates on a floor."""
    return spatial_service.create_resource_mapping_service(
        db=db, floor_id=floor_id, mapping_in=mapping_in
    )


@router.patch("/mappings/{mapping_id}", response_model=SpatialResourceMappingResponse)
def update_resource_mapping(
    mapping_id: int,
    update_in: SpatialResourceMappingUpdate,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Updates coordinates or properties of a mapped resource."""
    return spatial_service.update_resource_mapping_service(
        db=db, mapping_id=mapping_id, update_in=update_in
    )


@router.delete("/mappings/{mapping_id}")
def delete_resource_mapping(
    mapping_id: int,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Deletes a spatial mapping."""
    return spatial_service.delete_resource_mapping_service(db=db, mapping_id=mapping_id)


@router.get("/spatial/completeness", response_model=SpatialCompletenessReport)
def get_spatial_completeness(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Returns spatial mapping completeness metrics for staff oversight."""
    return spatial_service.get_spatial_completeness_report_service(db=db)

