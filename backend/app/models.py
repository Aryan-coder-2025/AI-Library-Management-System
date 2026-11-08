from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    Text,
    LargeBinary,
    DDL,
    event,
    JSON,
)
from sqlalchemy.orm import relationship, attributes, deferred

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = deferred(Column(String(50), unique=True, index=True, nullable=True))
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'student', 'teacher', or 'librarian'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    loans = relationship("Loan", back_populates="student", foreign_keys="Loan.student_id")
    issued_loans = relationship("Loan", back_populates="issued_by", foreign_keys="Loan.issued_by_id")
    reservations = relationship("Reservation", back_populates="user")
    search_events = relationship("SearchEvent", back_populates="user")
    inventory_events = relationship("InventoryEvent", back_populates="auditor")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan", lazy="select")
    holds = relationship("BookHold", back_populates="user", cascade="all, delete-orphan", lazy="select")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(255), nullable=False, index=True)
    isbn = Column(String(30), unique=True, nullable=True)
    category = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    
    # Vector embedding storage for semantic search
    embedding = Column(LargeBinary, nullable=True)
    embedding_updated_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    copies = relationship("BookCopy", back_populates="book", cascade="all, delete-orphan", passive_deletes=True)
    holds = relationship("BookHold", back_populates="book", cascade="all, delete-orphan", lazy="select")


@event.listens_for(Book, "before_update")
def _book_before_update(mapper, connection, target):
    """
    Advances updated_at when core book metadata fields are updated.
    Does not advance updated_at when only embedding vector storage is saved.
    """
    metadata_fields = {"title", "author", "isbn", "category", "description", "is_archived"}
    state = attributes.instance_state(target)
    for field in metadata_fields:
        hist = state.get_history(field, True)
        if hist.has_changes():
            target.updated_at = datetime.utcnow()
            break


class BookCopy(Base):
    __tablename__ = "book_copies"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False, index=True)
    copy_code = Column(String(50), unique=True, nullable=False, index=True)
    
    # Physical status: 'available', 'maintenance', 'lost', 'retired'
    # 'borrowed' is strictly derived from active loans and never stored here
    operational_status = Column(String(20), default="available", nullable=False)
    notes = Column(Text, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    book = relationship("Book", back_populates="copies")
    loans = relationship("Loan", back_populates="copy")
    inventory_events = relationship("InventoryEvent", back_populates="copy", cascade="all, delete-orphan", passive_deletes=True)


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    copy_id = Column(Integer, ForeignKey("book_copies.id", ondelete="RESTRICT"), nullable=False, index=True)
    issued_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    
    # NULL = active loan; non-NULL = returned loan
    returned_at = Column(DateTime, nullable=True, index=True)
    renewal_count = Column(Integer, default=0, nullable=False)

    student = relationship("User", foreign_keys=[student_id], back_populates="loans")
    issued_by = relationship("User", foreign_keys=[issued_by_id], back_populates="issued_loans")
    copy = relationship("BookCopy", foreign_keys=[copy_id], back_populates="loans")

    # Partial unique index: enforces at the database level that a copy can have at most one active loan
    __table_args__ = (
        Index(
            "uix_one_active_loan_per_copy",
            "copy_id",
            unique=True,
            sqlite_where=(returned_at.is_(None)),
        ),
    )


# ── Phase 1 Resource Management Models ───────────────────────────────────────

class StudyZone(Base):
    __tablename__ = "study_zones"

    id = Column(Integer, primary_key=True, index=True)
    zone_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    floor = Column(Integer, nullable=False)
    total_capacity = Column(Integer, nullable=False)
    noise_policy = Column(String(50), nullable=False, default="quiet")  # 'silent', 'quiet', 'collaborative'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    seats = relationship("StudySeat", back_populates="zone", cascade="all, delete-orphan", passive_deletes=True)
    observations = relationship("OccupancyObservation", back_populates="zone", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("floor >= 0", name="ck_study_zones_floor_nonneg"),
        CheckConstraint("total_capacity > 0", name="ck_study_zones_capacity_pos"),
        CheckConstraint("noise_policy IN ('silent', 'quiet', 'collaborative')", name="ck_study_zones_noise_policy"),
    )


class StudySeat(Base):
    __tablename__ = "study_seats"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("study_zones.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_code = Column(String(50), unique=True, nullable=False, index=True)
    has_power_outlet = Column(Boolean, default=True, nullable=False)
    has_monitor = Column(Boolean, default=False, nullable=False)
    is_accessible = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    zone = relationship("StudyZone", back_populates="seats")
    reservations = relationship("Reservation", back_populates="seat", cascade="all, delete-orphan", passive_deletes=True)


class StudyRoom(Base):
    __tablename__ = "study_rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    capacity = Column(Integer, nullable=False)
    display_type = Column(String(50), nullable=True)  # 'tv', 'projector', 'none'
    has_whiteboard = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reservations = relationship("Reservation", back_populates="room", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_study_rooms_capacity_pos"),
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    resource_type = Column(String(20), nullable=False, index=True)  # 'seat' or 'room'
    seat_id = Column(Integer, ForeignKey("study_seats.id", ondelete="CASCADE"), nullable=True, index=True)
    room_id = Column(Integer, ForeignKey("study_rooms.id", ondelete="CASCADE"), nullable=True, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default="active", nullable=False, index=True)  # 'active', 'completed', 'cancelled', 'no_show'
    checked_in_at = Column(DateTime, nullable=True, index=True)
    expected_attendees = Column(Integer, nullable=False, default=1, server_default="1")
    actual_attendees = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="reservations")
    seat = relationship("StudySeat", back_populates="reservations")
    room = relationship("StudyRoom", back_populates="reservations")

    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_reservations_time_order"),
        CheckConstraint("status IN ('active', 'completed', 'cancelled', 'no_show')", name="ck_reservations_status_valid"),
        CheckConstraint("resource_type IN ('seat', 'room')", name="ck_reservations_type_valid"),
        CheckConstraint(
            "(resource_type = 'seat' AND seat_id IS NOT NULL AND room_id IS NULL) OR "
            "(resource_type = 'room' AND room_id IS NOT NULL AND seat_id IS NULL)",
            name="ck_reservations_resource_target",
        ),
        CheckConstraint(
            "(resource_type = 'seat' AND expected_attendees = 1) OR "
            "(resource_type = 'room' AND expected_attendees >= 1)",
            name="ck_reservations_expected_attendees",
        ),
        CheckConstraint(
            "(resource_type = 'seat' AND (actual_attendees IS NULL OR actual_attendees = 1)) OR "
            "(resource_type = 'room' AND (actual_attendees IS NULL OR actual_attendees >= 1))",
            name="ck_reservations_actual_attendees",
        ),
        Index("ix_reservations_seat_active_window", "seat_id", "status", "start_time", "end_time"),
        Index("ix_reservations_room_active_window", "room_id", "status", "start_time", "end_time"),
        Index("ix_reservations_user_window", "user_id", "start_time", "end_time"),
    )


# Attach triggers for SQLite interval overlap prevention
_trg_seat_insert_ddl = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_seat_reservation_insert
BEFORE INSERT ON reservations
FOR EACH ROW
WHEN NEW.resource_type = 'seat' AND NEW.status = 'active'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM reservations
            WHERE seat_id = NEW.seat_id
              AND status = 'active'
              AND start_time < NEW.end_time
              AND end_time > NEW.start_time
        )
        THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
    END;
END;
""")

_trg_seat_update_ddl = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_seat_reservation_update
BEFORE UPDATE ON reservations
FOR EACH ROW
WHEN NEW.resource_type = 'seat' AND NEW.status = 'active'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM reservations
            WHERE seat_id = NEW.seat_id
              AND id != NEW.id
              AND status = 'active'
              AND start_time < NEW.end_time
              AND end_time > NEW.start_time
        )
        THEN RAISE(ABORT, 'Reservation conflict: seat is already reserved during this time interval.')
    END;
END;
""")

_trg_room_insert_ddl = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_room_reservation_insert
BEFORE INSERT ON reservations
FOR EACH ROW
WHEN NEW.resource_type = 'room' AND NEW.status = 'active'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM reservations
            WHERE room_id = NEW.room_id
              AND status = 'active'
              AND start_time < NEW.end_time
              AND end_time > NEW.start_time
        )
        THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
    END;
END;
""")

_trg_room_update_ddl = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_room_reservation_update
BEFORE UPDATE ON reservations
FOR EACH ROW
WHEN NEW.resource_type = 'room' AND NEW.status = 'active'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM reservations
            WHERE room_id = NEW.room_id
              AND id != NEW.id
              AND status = 'active'
              AND start_time < NEW.end_time
              AND end_time > NEW.start_time
        )
        THEN RAISE(ABORT, 'Reservation conflict: room is already reserved during this time interval.')
    END;
END;
""")

_trg_user_insert_ddl = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_user_reservation_overlap_insert
BEFORE INSERT ON reservations
FOR EACH ROW
WHEN NEW.status = 'active'
 AND COALESCE((SELECT role FROM users WHERE id = NEW.user_id), '') NOT IN ('librarian', 'admin')
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM reservations
            WHERE user_id = NEW.user_id
              AND status = 'active'
              AND start_time < NEW.end_time
              AND end_time > NEW.start_time
        )
        THEN RAISE(ABORT, 'Reservation conflict: user already has an active reservation during this time interval.')
    END;
END;
""")

_trg_user_update_ddl = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_user_reservation_overlap_update
BEFORE UPDATE ON reservations
FOR EACH ROW
WHEN NEW.status = 'active'
 AND COALESCE((SELECT role FROM users WHERE id = NEW.user_id), '') NOT IN ('librarian', 'admin')
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM reservations
            WHERE user_id = NEW.user_id
              AND id != NEW.id
              AND status = 'active'
              AND start_time < NEW.end_time
              AND end_time > NEW.start_time
        )
        THEN RAISE(ABORT, 'Reservation conflict: user already has an active reservation during this time interval.')
    END;
END;
""")

_trg_role_demotion_ddl = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_role_demotion_with_overlapping_reservations
BEFORE UPDATE OF role ON users
FOR EACH ROW
WHEN OLD.role IN ('librarian', 'admin')
 AND COALESCE(NEW.role, '') NOT IN ('librarian', 'admin')
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM reservations r1
            JOIN reservations r2 ON r1.user_id = r2.user_id AND r1.id < r2.id
            WHERE r1.user_id = NEW.id
              AND r1.status = 'active'
              AND r2.status = 'active'
              AND r1.start_time < r2.end_time
              AND r1.end_time > r2.start_time
        )
        THEN RAISE(ABORT, 'Role update rejected: user holds overlapping active reservations that violate student/teacher policy.')
    END;
END;
""")

event.listen(Reservation.__table__, "after_create", _trg_seat_insert_ddl.execute_if(dialect="sqlite"))
event.listen(Reservation.__table__, "after_create", _trg_seat_update_ddl.execute_if(dialect="sqlite"))
event.listen(Reservation.__table__, "after_create", _trg_room_insert_ddl.execute_if(dialect="sqlite"))
event.listen(Reservation.__table__, "after_create", _trg_room_update_ddl.execute_if(dialect="sqlite"))
event.listen(Reservation.__table__, "after_create", _trg_user_insert_ddl.execute_if(dialect="sqlite"))
event.listen(Reservation.__table__, "after_create", _trg_user_update_ddl.execute_if(dialect="sqlite"))
event.listen(User.__table__, "after_create", _trg_role_demotion_ddl.execute_if(dialect="sqlite"))


class OccupancyObservation(Base):
    __tablename__ = "occupancy_observations"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("study_zones.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    observed_count = Column(Integer, nullable=False)
    capacity_utilization = Column(Float, nullable=False)
    source_sensor_id = Column(String(50), nullable=True)

    zone = relationship("StudyZone", back_populates="observations")

    __table_args__ = (
        CheckConstraint("observed_count >= 0", name="ck_occupancy_count_nonneg"),
        CheckConstraint("capacity_utilization >= 0.0", name="ck_occupancy_util_nonneg"),
        Index("ix_occupancy_zone_time", "zone_id", "recorded_at"),
    )


class SearchEvent(Base):
    __tablename__ = "search_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    query_text = Column(String(500), nullable=False, index=True)
    search_type = Column(String(50), default="text", nullable=False, index=True)  # 'text', 'semantic', 'filter', 'copilot'
    results_count = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="search_events")

    __table_args__ = (
        CheckConstraint("results_count >= 0", name="ck_search_results_count_nonneg"),
        CheckConstraint("latency_ms >= 0", name="ck_search_latency_nonneg"),
        Index("ix_search_events_user_time", "user_id", "executed_at"),
        Index("ix_search_events_type_time", "search_type", "executed_at"),
    )


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    id = Column(Integer, primary_key=True, index=True)
    copy_id = Column(Integer, ForeignKey("book_copies.id", ondelete="CASCADE"), nullable=False, index=True)
    auditor_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # 'audit_scan', 'status_change', 'shelf_check', 'loss_reported', 'damage_flagged'
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    copy = relationship("BookCopy", back_populates="inventory_events")
    auditor = relationship("User", back_populates="inventory_events")

    __table_args__ = (
        Index("ix_inventory_events_copy_time", "copy_id", "recorded_at"),
        Index("ix_inventory_events_auditor_time", "auditor_id", "recorded_at"),
    )



class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="SET NULL"), nullable=True, index=True)
    notification_type = Column(String(50), nullable=False, index=True)  # 'overdue_alert', 'due_soon_reminder', 'loan_renewed', 'system_notice'
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    target_due_date = Column(Date, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    dedup_key = Column(String(255), unique=True, nullable=False, index=True)

    user = relationship("User")
    loan = relationship("Loan")

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read", "created_at"),
    )


# ── Stage 10.5 Spatial Models: Floor Plans, Resource Mapping & Wayfinding ─────

class LibraryFloor(Base):
    __tablename__ = "library_floors"

    id = Column(Integer, primary_key=True, index=True)
    floor_number = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)
    width = Column(Float, default=1000.0, nullable=False)
    height = Column(Float, default=700.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    published_layout_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="SET NULL", use_alter=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    layouts = relationship(
        "FloorPlan",
        foreign_keys="FloorPlan.floor_id",
        back_populates="floor",
        cascade="all, delete-orphan",
    )
    published_layout = relationship(
        "FloorPlan",
        foreign_keys=[published_layout_id],
        post_update=True,
    )
    resource_mappings = relationship(
        "SpatialResourceMapping",
        back_populates="floor",
        cascade="all, delete-orphan",
    )
    elements = relationship(
        "FloorPlanElement",
        back_populates="floor",
        cascade="all, delete-orphan",
    )
    wayfinding_nodes = relationship(
        "WayfindingNode",
        back_populates="floor",
        cascade="all, delete-orphan",
    )


class FloorPlan(Base):
    __tablename__ = "floor_plans"

    id = Column(Integer, primary_key=True, index=True)
    floor_id = Column(Integer, ForeignKey("library_floors.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="draft")  # 'draft', 'published', 'archived'
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    svg_viewbox = Column(String(50), default="0 0 1000 700", nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    floor = relationship("LibraryFloor", foreign_keys=[floor_id], back_populates="layouts")
    elements = relationship("FloorPlanElement", back_populates="layout", cascade="all, delete-orphan")
    created_by = relationship("User")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_floor_plans_status"),
        Index("ix_floor_plans_floor_status", "floor_id", "status"),
    )


class FloorPlanElement(Base):
    __tablename__ = "floor_plan_elements"

    id = Column(Integer, primary_key=True, index=True)
    floor_id = Column(Integer, ForeignKey("library_floors.id", ondelete="CASCADE"), nullable=False, index=True)
    layout_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="CASCADE"), nullable=True, index=True)
    element_type = Column(String(50), nullable=False, index=True)  # 'wall', 'door', 'entrance', 'exit', 'stairs', 'elevator', 'restroom', 'service_desk', 'label', 'facility', 'zone_boundary'
    label = Column(String(100), nullable=True)
    geometry_type = Column(String(20), nullable=False)  # 'rect', 'circle', 'polygon', 'path', 'text'
    geometry_data = Column(JSON, nullable=False)
    style_properties = Column(JSON, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    floor = relationship("LibraryFloor", back_populates="elements")
    layout = relationship("FloorPlan", back_populates="elements")


class SpatialResourceMapping(Base):
    __tablename__ = "spatial_resource_mappings"

    id = Column(Integer, primary_key=True, index=True)
    floor_id = Column(Integer, ForeignKey("library_floors.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(20), nullable=False, index=True)  # 'zone', 'room', 'seat'
    resource_id = Column(Integer, nullable=False, index=True)
    label = Column(String(100), nullable=True)
    x = Column(Float, nullable=False)  # normalized 0.0 to 1.0
    y = Column(Float, nullable=False)  # normalized 0.0 to 1.0
    width = Column(Float, nullable=True)  # normalized width
    height = Column(Float, nullable=True)  # normalized height
    rotation = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    floor = relationship("LibraryFloor", back_populates="resource_mappings")

    __table_args__ = (
        UniqueConstraint("resource_type", "resource_id", name="uq_spatial_resource_mapping"),
        CheckConstraint("resource_type IN ('zone', 'room', 'seat')", name="ck_spatial_resource_type"),
        CheckConstraint("x >= 0.0 AND x <= 1.05", name="ck_spatial_mapping_x_bounds"),
        CheckConstraint("y >= 0.0 AND y <= 1.05", name="ck_spatial_mapping_y_bounds"),
        Index("ix_spatial_mappings_floor_type", "floor_id", "resource_type"),
    )


class WayfindingNode(Base):
    __tablename__ = "wayfinding_nodes"

    id = Column(Integer, primary_key=True, index=True)
    floor_id = Column(Integer, ForeignKey("library_floors.id", ondelete="CASCADE"), nullable=False, index=True)
    node_type = Column(String(30), nullable=False, index=True)  # 'entrance', 'hallway', 'door', 'stairs', 'elevator', 'resource', 'service_desk'
    label = Column(String(100), nullable=True)
    x = Column(Float, nullable=False)  # normalized 0.0 to 1.0
    y = Column(Float, nullable=False)  # normalized 0.0 to 1.0
    resource_type = Column(String(20), nullable=True)
    resource_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    floor = relationship("LibraryFloor", back_populates="wayfinding_nodes")
    outgoing_edges = relationship(
        "WayfindingEdge",
        foreign_keys="WayfindingEdge.from_node_id",
        back_populates="from_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "WayfindingEdge",
        foreign_keys="WayfindingEdge.to_node_id",
        back_populates="to_node",
        cascade="all, delete-orphan",
    )


class WayfindingEdge(Base):
    __tablename__ = "wayfinding_edges"

    id = Column(Integer, primary_key=True, index=True)
    from_node_id = Column(Integer, ForeignKey("wayfinding_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    to_node_id = Column(Integer, ForeignKey("wayfinding_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    distance = Column(Float, nullable=False, default=1.0)
    is_accessible = Column(Boolean, default=True, nullable=False)
    edge_type = Column(String(20), default="walkway", nullable=False)  # 'walkway', 'door', 'stairs', 'elevator'

    from_node = relationship("WayfindingNode", foreign_keys=[from_node_id], back_populates="outgoing_edges")
    to_node = relationship("WayfindingNode", foreign_keys=[to_node_id], back_populates="incoming_edges")


# ── PILLAR 1: Knowledge Representation Models ────────────────────────────────

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    parent = relationship("Subject", remote_side=[id], backref="children")
    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")
    book_associations = relationship("BookSubject", back_populates="subject", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    subject = relationship("Subject", back_populates="topics")
    concepts = relationship("Concept", back_populates="topic", cascade="all, delete-orphan")
    book_associations = relationship("BookTopic", back_populates="topic", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("subject_id", "name", name="uq_topic_subject_name"),
    )


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    topic = relationship("Topic", back_populates="concepts")
    book_associations = relationship("BookConcept", back_populates="concept", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("topic_id", "name", name="uq_concept_topic_name"),
    )


class BookSubject(Base):
    __tablename__ = "book_subjects"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    book = relationship("Book")
    subject = relationship("Subject", back_populates="book_associations")

    __table_args__ = (
        UniqueConstraint("book_id", "subject_id", name="uq_book_subject"),
    )


class BookTopic(Base):
    __tablename__ = "book_topics"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    book = relationship("Book")
    topic = relationship("Topic", back_populates="book_associations")

    __table_args__ = (
        UniqueConstraint("book_id", "topic_id", name="uq_book_topic"),
    )


class BookConcept(Base):
    __tablename__ = "book_concepts"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    book = relationship("Book")
    concept = relationship("Concept", back_populates="book_associations")

    __table_args__ = (
        UniqueConstraint("book_id", "concept_id", name="uq_book_concept"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="reset_tokens")


class BookHold(Base):
    __tablename__ = "book_holds"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    copy_id = Column(Integer, ForeignKey("book_copies.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="waiting", nullable=False, index=True)  # 'waiting', 'ready_for_pickup', 'fulfilled', 'cancelled', 'expired'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    allocated_at = Column(DateTime, nullable=True)
    pickup_expires_at = Column(DateTime, nullable=True, index=True)
    fulfilled_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(String(255), nullable=True)

    book = relationship("Book", back_populates="holds")
    user = relationship("User", back_populates="holds")
    copy = relationship("BookCopy")


# ── Stage 12.14 Models: Academic Reserves, QR Collection, and Acquisitions ──

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "CS-301"
    title = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False, index=True)
    term = Column(String(50), nullable=False)  # e.g., "Fall 2026"
    instructor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    instructor = relationship("User", foreign_keys=[instructor_id])
    reading_list_items = relationship("CourseReadingListItem", back_populates="course", cascade="all, delete-orphan", lazy="select")
    reserves = relationship("CourseReserve", back_populates="course", cascade="all, delete-orphan", lazy="select")


class CourseReadingListItem(Base):
    __tablename__ = "course_reading_list_items"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    added_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    requirement_type = Column(String(50), default="required", nullable=False)  # 'required', 'recommended', 'supplementary'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="reading_list_items")
    book = relationship("Book")
    added_by = relationship("User")

    __table_args__ = (
        UniqueConstraint("course_id", "book_id", name="uq_course_book_reading_list"),
    )


class CourseReserve(Base):
    __tablename__ = "course_reserves"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    copy_id = Column(Integer, ForeignKey("book_copies.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    reserve_type = Column(String(20), default="2_hour", nullable=False)  # '2_hour', '24_hour'
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="reserves")
    copy = relationship("BookCopy")


class BookCollectionToken(Base):
    __tablename__ = "book_collection_tokens"

    id = Column(Integer, primary_key=True, index=True)
    hold_id = Column(Integer, ForeignKey("book_holds.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    hold = relationship("BookHold")
    user = relationship("User")


class AcquisitionRequest(Base):
    __tablename__ = "acquisition_requests"

    id = Column(Integer, primary_key=True, index=True)
    suggested_title = Column(String(255), nullable=False, index=True)
    suggested_author = Column(String(255), nullable=True)
    isbn = Column(String(20), nullable=True, index=True)
    search_query_origin = Column(String(255), nullable=True)
    frequency_score = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default="suggested", nullable=False, index=True)  # 'suggested', 'approved', 'rejected', 'ordered', 'received'
    requested_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    requested_by = relationship("User", foreign_keys=[requested_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


class InstitutionalInvitation(Base):
    __tablename__ = "institutional_invitations"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # 'teacher' or 'librarian'
    invite_code = Column(String(64), unique=True, index=True, nullable=False)
    invited_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)

    invited_by = relationship("User", foreign_keys=[invited_by_id])


