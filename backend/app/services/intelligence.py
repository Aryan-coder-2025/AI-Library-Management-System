"""
Librarian Intelligence Centre & Operational Analytics Service (INTEL-01, INTEL-02, INTEL-04).
Provides executive KPI snapshots, collection turnover metrics, degradation tracking, and circulation trends.
"""
from datetime import date, datetime, timedelta
import logging
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Book,
    BookCopy,
    BookHold,
    InventoryEvent,
    Loan,
    OccupancyObservation,
    Reservation,
    StudySeat,
)
from app.schemas import (
    CirculationDailyPoint,
    CirculationTrendsResponse,
    IntelligenceSnapshotResponse,
    InventoryAnalyticsResponse,
)

logger = logging.getLogger("athenaeum.intelligence")


def get_intelligence_snapshot_service(db: Session) -> IntelligenceSnapshotResponse:
    """Computes point-in-time executive KPI snapshot for library management."""
    today = date.today()
    now = datetime.utcnow()

    # Loans
    active_loans = db.execute(
        select(func.count(Loan.id)).where(Loan.returned_at.is_(None))
    ).scalar() or 0

    overdue_loans = db.execute(
        select(func.count(Loan.id)).where(
            Loan.returned_at.is_(None),
            Loan.due_date < today,
        )
    ).scalar() or 0

    overdue_rate = round((overdue_loans / max(active_loans, 1)) * 100.0, 1)

    # Catalog & Inventory
    total_books = db.execute(
        select(func.count(Book.id)).where(Book.is_archived == False)
    ).scalar() or 0

    total_copies = db.execute(select(func.count(BookCopy.id))).scalar() or 0

    # Holds
    active_holds = db.execute(
        select(func.count(BookHold.id)).where(
            BookHold.status.in_(["waiting", "ready_for_pickup"])
        )
    ).scalar() or 0

    # Space Reservations
    active_seats = db.execute(
        select(func.count(Reservation.id)).where(
            Reservation.seat_id.isnot(None),
            Reservation.status == "checked_in",
            Reservation.start_time <= now,
            Reservation.end_time >= now,
        )
    ).scalar() or 0

    active_rooms = db.execute(
        select(func.count(Reservation.id)).where(
            Reservation.room_id.isnot(None),
            Reservation.status == "checked_in",
            Reservation.start_time <= now,
            Reservation.end_time >= now,
        )
    ).scalar() or 0

    total_seats = db.execute(select(func.count(StudySeat.id))).scalar() or 150
    current_occupancy_pct = round((active_seats / max(total_seats, 1)) * 100.0, 1)

    # Peak Occupancy Hour
    peak_hour = 14  # Default 2:00 PM afternoon peak

    return IntelligenceSnapshotResponse(
        timestamp=now,
        active_loans_count=active_loans,
        overdue_loans_count=overdue_loans,
        overdue_rate_pct=overdue_rate,
        total_monographs=total_books,
        total_copies=total_copies,
        active_holds_count=active_holds,
        active_seat_reservations=active_seats,
        active_room_reservations=active_rooms,
        current_occupancy_pct=current_occupancy_pct,
        peak_occupancy_hour=peak_hour,
    )


def get_inventory_analytics_service(db: Session) -> InventoryAnalyticsResponse:
    """Computes collection health, turnover velocity, and degradation metrics."""
    total_books = db.execute(
        select(func.count(Book.id)).where(Book.is_archived == False)
    ).scalar() or 0

    total_copies = db.execute(select(func.count(BookCopy.id))).scalar() or 0

    # Active borrowed copies
    loaned_copy_ids = select(Loan.copy_id).where(Loan.returned_at.is_(None))
    borrowed_count = db.execute(
        select(func.count(BookCopy.id)).where(BookCopy.id.in_(loaned_copy_ids))
    ).scalar() or 0

    # Physical status counts
    avail_count = db.execute(
        select(func.count(BookCopy.id)).where(
            BookCopy.operational_status == "available",
            BookCopy.id.not_in(loaned_copy_ids),
        )
    ).scalar() or 0

    maint_count = db.execute(
        select(func.count(BookCopy.id)).where(BookCopy.operational_status == "maintenance")
    ).scalar() or 0

    lost_count = db.execute(
        select(func.count(BookCopy.id)).where(BookCopy.operational_status == "lost")
    ).scalar() or 0

    damaged_count = db.execute(
        select(func.count(BookCopy.id)).where(BookCopy.operational_status == "damaged")
    ).scalar() or 0

    # Lifetime loans count for turnover
    total_loans = db.execute(select(func.count(Loan.id))).scalar() or 0
    turnover_rate = round(total_loans / max(total_copies, 1), 2)

    # Monograph borrow velocity
    borrowed_book_ids = select(BookCopy.book_id).join(Loan, Loan.copy_id == BookCopy.id).distinct()
    borrowed_titles_count = db.execute(
        select(func.count(Book.id)).where(
            Book.is_archived == False,
            Book.id.in_(borrowed_book_ids),
        )
    ).scalar() or 0

    zero_borrow_titles = max(total_books - borrowed_titles_count, 0)
    high_demand_titles = db.execute(
        select(func.count(BookHold.book_id.distinct())).where(
            BookHold.status.in_(["waiting", "ready_for_pickup"])
        )
    ).scalar() or 0

    audit_events_count = db.execute(select(func.count(InventoryEvent.id))).scalar() or 0

    return InventoryAnalyticsResponse(
        total_monographs=total_books,
        total_physical_copies=total_copies,
        available_copies=avail_count,
        borrowed_copies=borrowed_count,
        maintenance_copies=maint_count,
        lost_copies=lost_count,
        damaged_copies=damaged_count,
        collection_turnover_rate=turnover_rate,
        zero_borrow_titles_count=zero_borrow_titles,
        high_demand_titles_count=high_demand_titles,
        total_audit_events_count=audit_events_count,
    )


def get_circulation_trends_service(db: Session, days: int = 30) -> CirculationTrendsResponse:
    """Computes daily circulation issues and returns over the given window."""
    today = date.today()
    start_date = today - timedelta(days=days)

    loans = db.execute(
        select(Loan).where(Loan.issued_at >= datetime.combine(start_date, datetime.min.time()))
    ).scalars().all()

    points_map = {}
    for i in range(days + 1):
        d_str = (start_date + timedelta(days=i)).isoformat()
        points_map[d_str] = {"issues": 0, "returns": 0, "renewals": 0}

    total_issues = 0
    total_returns = 0

    for loan in loans:
        issue_d = loan.issued_at.date().isoformat()
        if issue_d in points_map:
            points_map[issue_d]["issues"] += 1
            total_issues += 1

        if loan.returned_at:
            ret_d = loan.returned_at.date().isoformat()
            if ret_d in points_map:
                points_map[ret_d]["returns"] += 1
                total_returns += 1

        if getattr(loan, "renewal_count", 0) > 0:
            if issue_d in points_map:
                points_map[issue_d]["renewals"] += loan.renewal_count

    point_list = [
        CirculationDailyPoint(
            date=k,
            issues=v["issues"],
            returns=v["returns"],
            renewals=v["renewals"],
        )
        for k, v in sorted(points_map.items())
    ]

    return CirculationTrendsResponse(
        points=point_list,
        total_issues=total_issues,
        total_returns=total_returns,
        period_days=days,
    )

