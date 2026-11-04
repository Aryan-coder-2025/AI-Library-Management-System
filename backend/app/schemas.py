from datetime import datetime, date
import re
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_OPERATIONAL_STATUSES = {"available", "maintenance", "lost", "retired"}


def validate_isbn_string(isbn: str) -> str:
    """Validates ISBN-10 or ISBN-13 format and checksum."""
    cleaned = re.sub(r"[\s\-]", "", isbn)
    if len(cleaned) == 10:
        if not re.match(r"^\d{9}[\dX]$", cleaned, re.IGNORECASE):
            raise ValueError(f"Invalid ISBN-10 format: '{isbn}'")
        total = sum((10 - i) * (10 if c.upper() == "X" else int(c)) for i, c in enumerate(cleaned))
        if total % 11 != 0:
            raise ValueError(f"Invalid ISBN-10 checksum: '{isbn}'")
        return cleaned.upper()
    elif len(cleaned) == 13:
        if not re.match(r"^\d{13}$", cleaned):
            raise ValueError(f"Invalid ISBN-13 format: '{isbn}'")
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(cleaned))
        if total % 10 != 0:
            raise ValueError(f"Invalid ISBN-13 checksum: '{isbn}'")
        return cleaned
    else:
        raise ValueError(f"ISBN must be either 10 or 13 digits long, got {len(cleaned)} digits: '{isbn}'")


def validate_operational_status_value(status: str) -> str:
    """Validates physical copy operational status according to model conventions."""
    cleaned = status.strip().lower()
    if cleaned == "borrowed":
        raise ValueError(
            "Operational status cannot be 'borrowed'. Borrowed state is dynamically derived from active loans."
        )
    if cleaned not in VALID_OPERATIONAL_STATUSES:
        raise ValueError(
            f"Invalid operational status '{status}'. Must be one of: {', '.join(sorted(VALID_OPERATIONAL_STATUSES))}"
        )
    return cleaned


# ── System & Auth Schemas ─────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    project_name: str
    environment: str
    database: str
    demo_mode: bool = False


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, description="Account email address")
    password: str = Field(..., min_length=1, description="Account password")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class MessageResponse(BaseModel):
    message: str


# ── Catalogue Schemas ─────────────────────────────────────────────────────────

class BookBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Book title")
    author: str = Field(..., min_length=1, max_length=255, description="Author full name")
    isbn: Optional[str] = Field(None, max_length=30, description="ISBN-10 or ISBN-13")
    category: str = Field(..., min_length=1, max_length=100, description="Book category/genre")
    description: Optional[str] = Field(None, description="Detailed book description or synopsis")

    @field_validator("title", "author", "category")
    @classmethod
    def strip_and_validate_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only.")
        return cleaned

    @field_validator("isbn")
    @classmethod
    def check_isbn(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        return validate_isbn_string(cleaned)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    author: Optional[str] = Field(None, min_length=1, max_length=255)
    isbn: Optional[str] = Field(None, max_length=30)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_archived: Optional[bool] = None

    @field_validator("title", "author", "category")
    @classmethod
    def strip_and_validate_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only.")
        return cleaned

    @field_validator("isbn")
    @classmethod
    def check_isbn_update(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        return validate_isbn_string(cleaned)


class BookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    isbn: Optional[str] = None
    category: str
    description: Optional[str] = None
    is_archived: bool
    total_copies: int = 0
    available_copies: int = 0
    created_at: datetime
    updated_at: datetime


class BookPaginationResponse(BaseModel):
    items: List[BookResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Physical Copy Schemas ─────────────────────────────────────────────────────

class BookCopyCreate(BaseModel):
    copy_code: str = Field(..., min_length=1, max_length=50, description="Unique barcode or accession code")
    operational_status: str = Field("available", max_length=20, description="Status: available, maintenance, lost, retired")
    notes: Optional[str] = Field(None, description="Condition, edition, or shelf location notes")

    @field_validator("copy_code")
    @classmethod
    def strip_copy_code(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("copy_code cannot be empty or whitespace only.")
        return cleaned

    @field_validator("operational_status")
    @classmethod
    def check_operational_status(cls, v: str) -> str:
        return validate_operational_status_value(v)


class BookCopyUpdate(BaseModel):
    operational_status: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None

    @field_validator("operational_status")
    @classmethod
    def check_operational_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_operational_status_value(v)


class BookCopyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    copy_code: str
    operational_status: str
    is_borrowed: bool = False
    effective_status: str = "available"
    notes: Optional[str] = None
    added_at: datetime


class BookDetailResponse(BookResponse):
    copies: List[BookCopyResponse] = []


# ── Loan Circulation Schemas ──────────────────────────────────────────────────

class LoanIssueRequest(BaseModel):
    student_id: int = Field(..., gt=0, description="ID of the student borrowing the physical copy")
    copy_id: int = Field(..., gt=0, description="ID of the physical book copy being borrowed")


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    copy_id: int
    copy_code: str
    book_id: int
    book_title: str
    book_author: Optional[str] = None
    issued_by_id: int
    issued_at: datetime
    due_date: date
    returned_at: Optional[datetime] = None
    status: str = Field(..., description="'active', 'returned', or 'overdue'")
    is_overdue: bool = False
    renewal_count: int = 0


class LoanPaginationResponse(BaseModel):
    items: List[LoanResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Stage 5: Semantic Search & Recommendation Schemas ─────────────────────────

class SemanticBookResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    isbn: Optional[str] = None
    category: str
    description: Optional[str] = None
    total_copies: int = 0
    available_copies: int = 0
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score (-1.0 to 1.0) between query and book embedding. "
                    "Note: This is a geometric vector similarity metric, not a probability or accuracy score."
    )


class SemanticSearchResponse(BaseModel):
    items: List[SemanticBookResult]
    total: int
    page: int
    page_size: int
    total_pages: int
    query: str
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    disclaimer: str = (
        "Similarity scores represent vector cosine similarity (-1.0 to 1.0) based on title, author, "
        "category, and description embeddings. They do not indicate probability or retrieval accuracy."
    )


class HybridBookResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    isbn: Optional[str] = None
    category: str
    description: Optional[str] = None
    total_copies: int = 0
    available_copies: int = 0
    rrf_score: float = Field(..., description="Reciprocal Rank Fusion score combining lexical and semantic rankings.")
    lexical_rank: Optional[int] = Field(None, description="1-based position in lexical candidate ranking if matched.")
    semantic_rank: Optional[int] = Field(None, description="1-based position in semantic vector candidate ranking if matched.")
    similarity_score: Optional[float] = Field(None, description="Cosine similarity score (-1.0 to 1.0) if vector matched.")
    match_channels: List[str] = Field(default_factory=list, description="Channels that matched: 'lexical', 'semantic', 'exact_identifier'.")


class HybridSearchResponse(BaseModel):
    items: List[HybridBookResult]
    total: int
    page: int
    page_size: int
    total_pages: int
    total_lexical_matches: int
    total_semantic_matches: int
    total_fused_candidates: int
    query: str
    applied_category: Optional[str] = None
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    fusion_method: str = "Reciprocal Rank Fusion (k=60)"


class BookRecommendationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    isbn: Optional[str] = None
    category: str
    description: Optional[str] = None
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score (-1.0 to 1.0) compared with the selected source book."
    )


class BookRecommendationResponse(BaseModel):
    source_book_id: int
    source_book_title: str
    recommendations: List[BookRecommendationResult]
    total: int
    method: str = "content-based-cosine-similarity"
    disclaimer: str = (
        "Recommendations are content-based comparisons derived from title, author, category, and "
        "description text embeddings. They are not personalized or learned from student borrowing histories."
    )


class EmbeddingStatusResponse(BaseModel):
    total_books: int
    with_embedding: int
    missing_embedding: int
    stale_embedding: int
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    model_available: bool
    is_processing: bool = False


class EmbeddingRefreshResponse(BaseModel):
    status: str
    total_candidates: int
    processed: int
    failed: int
    stale: int
    missing: int
    message: str
    errors: List[str] = []


# ── AI Copilot Schemas ────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., max_length=2000)


class CopilotSource(BaseModel):
    type: str = Field(..., description="'book', 'policy', or 'loan'")
    id: Optional[int] = None
    title: str
    snippet: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    available_copies: Optional[int] = None
    total_copies: Optional[int] = None


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    conversation_history: List[ChatMessage] = Field(default_factory=list, max_length=20)


class CopilotChatResponse(BaseModel):
    reply: str
    provider: str  # 'gemini', 'openai_compatible', 'fallback'
    is_fallback: bool
    sources: List[CopilotSource] = []
    suggested_followups: List[str] = []


# ── Stage 9: Patron Profile & Notification Schemas ───────────────────────────

class PatronProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=2, max_length=100, description="Patron full name")

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return cleaned


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1, description="Current account password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New secure password")

    @field_validator("new_password")
    @classmethod
    def check_password_policy(cls, v: str) -> str:
        from app.auth import validate_password_policy
        return validate_password_policy(v)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    loan_id: Optional[int] = None
    notification_type: str
    title: str
    message: str
    target_due_date: Optional[date] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationPaginationResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class SweepNotificationResponse(BaseModel):
    new_notifications: int


# ── Study Space Schemas ───────────────────────────────────────────────────────

class StudyZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_code: str
    name: str
    floor: int
    total_capacity: int
    noise_policy: str
    is_active: bool
    created_at: datetime


class StudySeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    seat_code: str
    has_power_outlet: bool
    has_monitor: bool
    is_accessible: bool
    is_active: bool
    created_at: datetime


class StudyRoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_code: str
    name: str
    capacity: int
    display_type: Optional[str] = None
    has_whiteboard: bool
    is_active: bool
    created_at: datetime


class ReservationBase(BaseModel):
    resource_type: str = Field(..., pattern="^(seat|room)$")
    seat_id: Optional[int] = None
    room_id: Optional[int] = None
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_resource_target_and_times(self) -> "ReservationBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time.")
        if self.resource_type == "seat":
            if self.seat_id is None or self.room_id is not None:
                raise ValueError("Seat reservations must specify seat_id and omit room_id.")
        elif self.resource_type == "room":
            if self.room_id is None or self.seat_id is not None:
                raise ValueError("Room reservations must specify room_id and omit seat_id.")
        return self


class ReservationCreate(ReservationBase):
    expected_attendees: Optional[int] = 1

    @field_validator("expected_attendees", mode="before")
    @classmethod
    def validate_expected_attendees(cls, v: Any) -> Any:
        if v is None:
            return 1
        if isinstance(v, bool):
            raise ValueError("Attendee count must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("Attendee count must be an integer.")
        if v < 1:
            raise ValueError("Attendee count must be at least 1.")
        return v

    @model_validator(mode="after")
    def validate_seat_expected_attendees(self) -> "ReservationCreate":
        if self.resource_type == "seat" and self.expected_attendees != 1:
            raise ValueError("Seat reservations must have exactly 1 expected attendee.")
        return self


class ReservationCheckInRequest(BaseModel):
    actual_attendees: Optional[int] = None

    @field_validator("actual_attendees", mode="before")
    @classmethod
    def validate_actual_attendees(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("Actual attendee count must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("Actual attendee count must be an integer.")
        if v < 1:
            raise ValueError("Actual attendee count must be at least 1.")
        return v


class ReservationCheckInWithTokenRequest(BaseModel):
    token: str
    actual_attendees: Optional[int] = None

    @field_validator("actual_attendees", mode="before")
    @classmethod
    def validate_actual_attendees(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("Actual attendee count must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("Actual attendee count must be an integer.")
        if v < 1:
            raise ValueError("Actual attendee count must be at least 1.")
        return v


class ReservationQRResponse(BaseModel):
    reservation_id: int
    qr_token: str
    expires_at: datetime
    start_time: datetime
    end_time: datetime
    resource_type: str
    resource_name: str
    checkin_window_start: datetime
    checkin_window_end: datetime


class ReservationSweepReport(BaseModel):
    processed_count: int
    no_show_count: int
    completed_count: int
    no_show_reservation_ids: List[int]
    completed_reservation_ids: List[int]


class ReservationResponse(ReservationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    checked_in_at: Optional[datetime] = None
    expected_attendees: int
    actual_attendees: Optional[int] = None
    created_at: datetime


class ReservationPaginationResponse(BaseModel):
    items: List[ReservationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SpaceAvailabilityResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    seats: List[StudySeatResponse] = []
    rooms: List[StudyRoomResponse] = []
    total_available_seats: int = 0
    total_available_rooms: int = 0


# ── Stage 10.4: Occupancy Tracking, Telemetry & Analytics Schemas ─────────────

class ZoneOccupancySummary(BaseModel):
    zone_id: int
    zone_code: str
    name: str
    floor: int
    noise_policy: str
    total_capacity: int
    occupied_seats: int
    available_seats: int
    utilization_percentage: float


class RoomOccupancySummary(BaseModel):
    room_id: int
    room_code: str
    name: str
    capacity: int
    display_type: Optional[str] = None
    has_whiteboard: bool
    is_active: bool
    is_occupied: bool
    current_attendees: int
    active_reservation_id: Optional[int] = None


class CurrentOccupancyResponse(BaseModel):
    total_library_occupancy: int
    total_library_capacity: int
    total_library_available: int
    overall_utilization_percentage: float
    occupied_seats: int
    total_seats: int
    seat_utilization_percentage: float
    occupied_room_attendees: int
    total_room_capacity: int
    room_attendees_utilization_percentage: float
    active_rooms_count: int
    total_rooms_count: int
    zones: List[ZoneOccupancySummary]
    rooms: List[RoomOccupancySummary]
    provenance: str = "reservation_estimate"
    as_of: datetime


class ResourceSeatBreakdown(BaseModel):
    total_seats: int
    occupied_seats: int
    available_seats: int
    utilization_percentage: float
    power_outlet_seats_count: int
    monitor_seats_count: int
    accessible_seats_count: int


class ResourceRoomBreakdown(BaseModel):
    total_rooms: int
    active_occupied_rooms: int
    total_room_capacity: int
    occupied_room_attendees: int
    available_room_capacity: int
    utilization_percentage: float
    rooms: List[RoomOccupancySummary]


class ResourceOccupancyResponse(BaseModel):
    seats: ResourceSeatBreakdown
    rooms: ResourceRoomBreakdown
    provenance: str = "reservation_estimate"
    as_of: datetime


class HistoricalOccupancyDataPoint(BaseModel):
    time_bucket: str
    zone_id: Optional[int] = None
    avg_observed_count: float
    max_observed_count: int
    min_observed_count: int
    avg_capacity_utilization: float
    observation_count: int


class HistoricalOccupancyResponse(BaseModel):
    interval: str  # 'hour' or 'day'
    zone_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    total_observations: int
    overall_avg_occupancy: float
    overall_peak_occupancy: int
    overall_avg_utilization: float
    data_points: List[HistoricalOccupancyDataPoint]
    provenance: str = "recorded_telemetry"


class PeakUsageHourSummary(BaseModel):
    hour_of_day: int  # 0 to 23
    avg_observed_count: float
    peak_observed_count: int
    avg_utilization_percentage: float
    observation_count: int
    is_peak: bool = False


class PeakUsageAnalysisResponse(BaseModel):
    zone_id: Optional[int] = None
    days_analyzed: int
    total_observations: int
    peak_hour: int
    peak_hour_avg_occupancy: float
    lowest_hour: int
    hourly_distribution: List[PeakUsageHourSummary]
    provenance: str = "recorded_telemetry"


class TelemetryObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: int
    recorded_at: Optional[datetime] = None
    observed_count: int = Field(..., ge=0, description="Observed headcount in study zone")
    source_sensor_id: Optional[str] = Field(None, max_length=50)


class TelemetryObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    recorded_at: datetime
    observed_count: int
    capacity_utilization: float
    source_sensor_id: Optional[str] = None
    status: str = "recorded"


