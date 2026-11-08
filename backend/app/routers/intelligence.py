"""
FastAPI Router for Librarian Intelligence Centre, Demand Forecasting & Acquisitions (INTEL-01 to INTEL-05).
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_user, require_librarian
from app.models import User
from app.schemas import (
    AcquisitionRequestCreate,
    AcquisitionRequestListResponse,
    AcquisitionRequestResponse,
    AcquisitionRequestUpdate,
    AcquisitionSuggestionListResponse,
    CirculationTrendsResponse,
    IntelligenceSnapshotResponse,
    InventoryAnalyticsResponse,
    TwoWeekDemandForecastResponse,
)
from app.services.acquisitions import (
    create_acquisition_request_service,
    get_acquisition_suggestions_service,
    list_acquisition_requests_service,
    update_acquisition_request_service,
)
from app.services.forecasting import calculate_two_week_demand_forecast
from app.services.intelligence import (
    get_circulation_trends_service,
    get_intelligence_snapshot_service,
    get_inventory_analytics_service,
)

router = APIRouter(prefix="/api/intelligence", tags=["Librarian Intelligence & Analytics"])


@router.get(
    "/snapshot",
    response_model=IntelligenceSnapshotResponse,
    summary="Executive KPI intelligence snapshot",
)
def get_snapshot(
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Returns point-in-time executive snapshot of library activity."""
    return get_intelligence_snapshot_service(db)


@router.get(
    "/inventory",
    response_model=InventoryAnalyticsResponse,
    summary="Collection turnover and inventory degradation analytics",
)
def get_inventory(
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Returns collection turnover rate, status distribution, and health metrics."""
    return get_inventory_analytics_service(db)


@router.get(
    "/circulation-trends",
    response_model=CirculationTrendsResponse,
    summary="Daily circulation issue, return, and renewal trends",
)
def get_circulation_trends(
    days: int = Query(30, ge=7, le=90, description="Window in days"),
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Returns daily historical circulation issue/return counts."""
    return get_circulation_trends_service(db, days=days)


@router.get(
    "/forecast",
    response_model=TwoWeekDemandForecastResponse,
    summary="Two-week predictive checkout demand forecast",
)
def get_demand_forecast(
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Returns 14-day checkout demand projection with 95% confidence intervals."""
    return calculate_two_week_demand_forecast(db)


@router.get(
    "/acquisitions/suggestions",
    response_model=AcquisitionSuggestionListResponse,
    summary="Zero-result search telemetry acquisition signals",
)
def get_acquisition_suggestions(
    limit: int = Query(25, ge=5, le=100),
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Aggregates zero-result searches into demand signals for collection procurement."""
    return get_acquisition_suggestions_service(db, limit=limit)


@router.get(
    "/acquisitions/requests",
    response_model=AcquisitionRequestListResponse,
    summary="List collection development acquisition requests",
)
def list_acquisition_requests(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_db),
):
    """Lists collection development requests and current review states."""
    return list_acquisition_requests_service(db, status_filter=status_filter)


@router.post(
    "/acquisitions/requests",
    response_model=AcquisitionRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit acquisition candidate request",
)
def create_acquisition_request(
    req: AcquisitionRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_write_db),
):
    """Submits a candidate book purchase request for review."""
    return create_acquisition_request_service(db, current_user, req)


@router.patch(
    "/acquisitions/requests/{request_id}",
    response_model=AcquisitionRequestResponse,
    summary="Review and advance acquisition request",
)
def update_acquisition_request(
    request_id: int,
    req: AcquisitionRequestUpdate,
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """Advances acquisition status ('approved', 'rejected', 'ordered', 'received') with review notes."""
    return update_acquisition_request_service(db, current_user, request_id, req)

