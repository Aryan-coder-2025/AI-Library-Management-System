"""
Notifications API router (CIRC-04).
Provides endpoints for patron alerts, unread counts, status updates, and librarian sweeps.
"""
from datetime import date
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user, require_librarian
from app.models import User
from app.schemas import (
    NotificationResponse,
    NotificationPaginationResponse,
    NotificationUnreadCountResponse,
    SweepNotificationResponse,
)
from app.services import notifications as notifications_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=NotificationPaginationResponse,
    summary="List authenticated user's notifications",
)
def list_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns paginated notifications for the authenticated patron or staff member.
    """
    return notifications_service.list_user_notifications_service(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )


@router.get(
    "/unread-count",
    response_model=NotificationUnreadCountResponse,
    summary="Get count of unread notifications for current user",
)
def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns the real-time unread count for badge indicators in UI header.
    """
    return notifications_service.get_unread_count_service(
        db=db,
        user_id=current_user.id,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a specific notification as read",
)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Marks a notification as read. The notification must belong to the caller.
    """
    return notifications_service.mark_notification_read_service(
        db=db,
        notification_id=notification_id,
        current_user=current_user,
    )


@router.post(
    "/mark-all-read",
    response_model=Dict[str, Any],
    summary="Mark all unread notifications as read for current user",
)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Bulk marks all unread notifications for the caller as read.
    """
    return notifications_service.mark_all_notifications_read_service(
        db=db,
        user_id=current_user.id,
    )


@router.delete(
    "/clear-all",
    response_model=Dict[str, Any],
    summary="Delete all notifications for current user",
)
def clear_all_notifications(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Clears / deletes all notifications for the caller.
    """
    return notifications_service.clear_all_user_notifications_service(
        db=db,
        user_id=current_user.id,
    )


@router.delete(
    "/{notification_id}",
    response_model=Dict[str, Any],
    summary="Delete a specific notification",
)
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_write_db),
):
    """
    Deletes a notification belonging to the caller.
    """
    return notifications_service.delete_notification_service(
        db=db,
        notification_id=notification_id,
        current_user=current_user,
    )


@router.post(
    "/sweep",
    response_model=SweepNotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger an overdue notification sweep (librarian only)",
)
def sweep_overdue_notifications(
    as_of_date: Optional[date] = Query(None, description="Optional baseline evaluation date (defaults to today)"),
    current_user: User = Depends(require_librarian),
    db: Session = Depends(get_write_db),
):
    """
    Manually triggers an overdue sweep across all active loans.
    Creates deduplicated in-app notifications for overdue items.
    Librarian only.
    """
    return notifications_service.sweep_and_generate_overdue_notifications(
        db=db,
        as_of_date=as_of_date,
    )

