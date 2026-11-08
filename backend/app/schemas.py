from datetime import datetime, date
import re
from typing import Any, Dict, List, Optional
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
    identifier: Optional[str] = Field(None, min_length=1, max_length=255, description="Email address or username")
    email: Optional[str] = Field(None, min_length=1, max_length=255, description="Email address or username (alias)")
    username: Optional[str] = Field(None, min_length=1, max_length=255, description="Username or email (alias)")
    password: str = Field(..., min_length=1, description="Account password")

    @model_validator(mode="after")
    def resolve_login_identifier(self) -> "LoginRequest":
        effective = self.identifier or self.email or self.username
        if not effective or not effective.strip():
            raise ValueError("Email address or username is required.")
        self.identifier = effective.strip()
        self.email = self.identifier
        return self


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=2, max_length=100, description="Patron full name")
    email: str = Field(..., min_length=3, max_length=255, description="Valid email address")
    username: str = Field(..., min_length=3, max_length=20, description="Unique username")
    password: str = Field(..., min_length=12, max_length=100, description="Password (min 12 characters)")
    confirm_password: Optional[str] = Field(None, min_length=1, description="Password confirmation")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        from app.cli import validate_email
        return validate_email(v)

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        from app.auth import validate_username
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        from app.auth import validate_password_policy
        return validate_password_policy(v)

    @model_validator(mode="after")
    def verify_password_match(self) -> "RegisterRequest":
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class InstitutionalRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    email: str = Field(..., min_length=3, max_length=255, description="Valid email address")
    username: str = Field(..., min_length=3, max_length=20, description="Unique username")
    password: str = Field(..., min_length=12, max_length=100, description="Password (min 12 characters)")
    confirm_password: Optional[str] = Field(None, min_length=1, description="Password confirmation")
    role: str = Field("student", description="Requested role: student, teacher, or librarian")
    verification_key: Optional[str] = Field(None, description="Department passkey or invite code")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        from app.cli import validate_email
        return validate_email(v)

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        from app.auth import validate_username
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        from app.auth import validate_password_policy
        return validate_password_policy(v)

    @field_validator("role")
    @classmethod
    def validate_role_field(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in ("student", "teacher", "librarian"):
            raise ValueError("Role must be 'student', 'teacher', or 'librarian'.")
        return cleaned

    @model_validator(mode="after")
    def verify_password_match(self) -> "InstitutionalRegisterRequest":
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class CreateInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255, description="Email to invite")
    role: str = Field("teacher", description="Role: teacher or librarian")

    @field_validator("email")
    @classmethod
    def validate_invite_email(cls, v: str) -> str:
        from app.cli import validate_email
        return validate_email(v)

    @field_validator("role")
    @classmethod
    def validate_invite_role(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in ("teacher", "librarian"):
            raise ValueError("Invited role must be 'teacher' or 'librarian'.")
        return cleaned


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    invite_code: str
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime] = None
    is_used: bool = False


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: Optional[str] = None
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

    full_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Patron full name")
    username: Optional[str] = Field(None, min_length=3, max_length=20, description="Patron username")

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return cleaned

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        from app.auth import validate_username
        return validate_username(v)

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "PatronProfileUpdate":
        if self.full_name is None and self.username is None:
            raise ValueError("At least one profile field (full_name or username) must be provided.")
        return self


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1, description="Current account password")
    new_password: str = Field(..., min_length=12, max_length=100, description="New secure password")

    @field_validator("new_password")
    @classmethod
    def check_password_policy(cls, v: str) -> str:
        from app.auth import validate_password_policy
        return validate_password_policy(v)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255, description="Registered email address")

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        from app.cli import validate_email
        return validate_email(v)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=10, max_length=128, description="Cryptographic password reset token")
    new_password: str = Field(..., min_length=12, max_length=100, description="New password (minimum 12 characters)")
    confirm_password: Optional[str] = Field(None, min_length=1, description="Password confirmation")

    @field_validator("new_password")
    @classmethod
    def validate_new_password_field(cls, v: str) -> str:
        from app.auth import validate_password_policy
        return validate_password_policy(v)

    @model_validator(mode="after")
    def verify_password_match(self) -> "ResetPasswordRequest":
        if self.confirm_password is not None and self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class InstitutionalRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    email: str = Field(..., min_length=3, max_length=255, description="Valid email address")
    username: str = Field(..., min_length=3, max_length=20, description="Unique username")
    password: str = Field(..., min_length=12, max_length=100, description="Password (min 12 characters)")
    confirm_password: Optional[str] = Field(None, min_length=1, description="Password confirmation")
    role: str = Field("student", description="Requested role: student, teacher, or librarian")
    verification_key: Optional[str] = Field(None, description="Department passkey or invite code")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        from app.cli import validate_email
        return validate_email(v)

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        from app.auth import validate_username
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        from app.auth import validate_password_policy
        return validate_password_policy(v)

    @field_validator("role")
    @classmethod
    def validate_role_field(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in ("student", "teacher", "librarian"):
            raise ValueError("Role must be 'student', 'teacher', or 'librarian'.")
        return cleaned

    @model_validator(mode="after")
    def verify_password_match(self) -> "InstitutionalRegisterRequest":
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class CreateInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255, description="Email to invite")
    role: str = Field("teacher", description="Role: teacher or librarian")

    @field_validator("email")
    @classmethod
    def validate_invite_email(cls, v: str) -> str:
        from app.cli import validate_email
        return validate_email(v)

    @field_validator("role")
    @classmethod
    def validate_invite_role(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in ("teacher", "librarian"):
            raise ValueError("Invited role must be 'teacher' or 'librarian'.")
        return cleaned


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    invite_code: str
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime] = None
    is_used: bool = False


# ── Book Waitlists & Holds (CIRC-02) ─────────────────────────────────────────

class BookHoldCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: int = Field(..., gt=0, description="Target book monograph ID")


class BookHoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    book_title: str
    book_author: Optional[str] = None
    book_isbn: Optional[str] = None
    user_id: int
    patron_name: Optional[str] = None
    copy_id: Optional[int] = None
    copy_code: Optional[str] = None
    status: str
    queue_position: Optional[int] = None
    created_at: datetime
    allocated_at: Optional[datetime] = None
    pickup_expires_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None


class BookHoldListResponse(BaseModel):
    total: int
    items: List[BookHoldResponse]


# ── External Academic Research Discovery ─────────────────────────────────────

class AcademicPaperResult(BaseModel):
    id: str
    title: str
    authors: List[str] = []
    abstract: Optional[str] = None
    publication_year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    venue: Optional[str] = None
    source_provider: str  # 'openalex', 'arxiv', 'crossref'
    open_access: bool = False
    url: Optional[str] = None
    citation_count: Optional[int] = None


class AcademicSearchResponse(BaseModel):
    query: str
    total_results: int
    page: int
    page_size: int
    providers_queried: List[str]
    active_providers: List[str]
    results: List[AcademicPaperResult]
    ai_research_notes: Optional[str] = None
    focused_topic: Optional[str] = None


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
    observed_count: int = Field(..., description="Observed headcount in study zone")
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


# ── Stage 10.5 Spatial Schemas: Floors, Floor Plans, Mapping & Wayfinding ─────

class LibraryFloorBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    floor_number: int = Field(..., ge=0, description="Floor level identifier (0=Ground, 1=First, etc.)")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    display_order: int = Field(0, description="Display sorting order")
    width: float = Field(1000.0, gt=0, description="Canvas coordinate width")
    height: float = Field(700.0, gt=0, description="Canvas coordinate height")
    is_active: bool = True


class LibraryFloorCreate(LibraryFloorBase):
    pass


class LibraryFloorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    display_order: Optional[int] = None
    width: Optional[float] = Field(None, gt=0)
    height: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None


class LibraryFloorResponse(LibraryFloorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    published_layout_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class FloorPlanElementBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_type: str = Field(..., max_length=50, description="wall, door, entrance, exit, stairs, elevator, restroom, service_desk, label, facility, zone_boundary")
    label: Optional[str] = Field(None, max_length=100)
    geometry_type: str = Field(..., description="rect, circle, polygon, path, text")
    geometry_data: Dict[str, Any] = Field(..., description="Normalized coordinates and dimensional attributes")
    style_properties: Optional[Dict[str, Any]] = None
    display_order: int = 0
    is_active: bool = True


class FloorPlanElementCreate(FloorPlanElementBase):
    layout_id: Optional[int] = None


class FloorPlanElementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_type: Optional[str] = Field(None, max_length=50)
    label: Optional[str] = Field(None, max_length=100)
    geometry_type: Optional[str] = None
    geometry_data: Optional[Dict[str, Any]] = None
    style_properties: Optional[Dict[str, Any]] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class FloorPlanElementResponse(FloorPlanElementBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    floor_id: int
    layout_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class FloorPlanBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    svg_viewbox: str = Field("0 0 1000 700", max_length=50)


class FloorPlanCreate(FloorPlanBase):
    pass


class FloorPlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    svg_viewbox: Optional[str] = Field(None, max_length=50)


class FloorPlanResponse(FloorPlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    floor_id: int
    version: int
    status: str
    created_by_user_id: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SpatialResourceMappingBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: str = Field(..., description="'zone', 'room', or 'seat'")
    resource_id: int = Field(..., gt=0)
    label: Optional[str] = Field(None, max_length=100)
    x: float = Field(..., ge=0.0, le=1.05, description="Normalized X coordinate [0.0 - 1.0]")
    y: float = Field(..., ge=0.0, le=1.05, description="Normalized Y coordinate [0.0 - 1.0]")
    width: Optional[float] = Field(None, gt=0.0, le=1.0)
    height: Optional[float] = Field(None, gt=0.0, le=1.0)
    rotation: float = Field(0.0, ge=0.0, le=360.0)
    is_active: bool = True

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, v: str) -> str:
        if v not in ("zone", "room", "seat"):
            raise ValueError("resource_type must be 'zone', 'room', or 'seat'")
        return v


class SpatialResourceMappingCreate(SpatialResourceMappingBase):
    pass


class SpatialResourceMappingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Optional[str] = Field(None, max_length=100)
    x: Optional[float] = Field(None, ge=0.0, le=1.05)
    y: Optional[float] = Field(None, ge=0.0, le=1.05)
    width: Optional[float] = Field(None, gt=0.0, le=1.0)
    height: Optional[float] = Field(None, gt=0.0, le=1.0)
    rotation: Optional[float] = Field(None, ge=0.0, le=360.0)
    is_active: Optional[bool] = None


class SpatialResourceMappingResponse(SpatialResourceMappingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    floor_id: int
    created_at: datetime
    updated_at: datetime


class SpatialResourceAvailability(BaseModel):
    resource_type: str  # 'seat', 'room', 'zone'
    resource_id: int
    label: Optional[str] = None
    availability_status: str  # 'available', 'reserved', 'occupied', 'unavailable', 'unknown'
    current_attendees: Optional[int] = None
    capacity: Optional[int] = None
    provenance: str = "reservation_state"
    x: float
    y: float
    width: Optional[float] = None
    height: Optional[float] = None
    rotation: float = 0.0
    zone_id: Optional[int] = None
    zone_code: Optional[str] = None
    zone_name: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class FloorPlanDetailResponse(BaseModel):
    floor: LibraryFloorResponse
    layout: Optional[FloorPlanResponse] = None
    elements: List[FloorPlanElementResponse] = []
    resources: List[SpatialResourceAvailability] = []
    is_demonstration_layout: bool = True
    disclosure: str = "ILLUSTRATIVE DEMONSTRATION LAYOUT — NOT A SURVEYED BUILDING PLAN"


class ResourceLocationResponse(BaseModel):
    resource_type: str
    resource_id: int
    label: Optional[str] = None
    floor_id: int
    floor_number: int
    floor_name: str
    zone_id: Optional[int] = None
    zone_code: Optional[str] = None
    zone_name: Optional[str] = None
    x: float
    y: float
    availability_status: str
    directional_guidance: Optional[str] = None
    is_demonstration: bool = True
    disclosure: str = "ILLUSTRATIVE DEMONSTRATION LAYOUT — NOT A SURVEYED BUILDING PLAN"


class WayfindingStep(BaseModel):
    step_number: int
    instruction: str
    floor_number: int
    node_type: str
    x: float
    y: float


class WayfindingRouteResponse(BaseModel):
    destination_resource_type: str
    destination_resource_id: int
    destination_label: str
    destination_floor_number: int
    total_distance: float
    is_accessible: bool
    path_points: List[List[float]]
    steps: List[WayfindingStep]
    is_demonstration: bool = True
    disclosure: str = "ILLUSTRATIVE DEMONSTRATION ROUTE — FOR VISUAL WAYFINDING GUIDANCE ONLY"


class SpatialCompletenessReport(BaseModel):
    total_zones: int
    mapped_zones: int
    unmapped_zone_ids: List[int]
    total_seats: int
    mapped_seats: int
    unmapped_seat_ids: List[int]
    total_rooms: int
    mapped_rooms: int
    unmapped_room_ids: List[int]
    mapping_completeness_percentage: float
    published_floors_count: int
    draft_floors_count: int


# ── PILLAR 1: Knowledge Representation Schemas ────────────────────────────────

class ConceptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    name: str
    description: Optional[str] = None
    concepts: List[ConceptResponse] = []
    created_at: datetime


class SubjectTreeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    children: List['SubjectTreeResponse'] = []
    topics: List[TopicResponse] = []
    created_at: datetime


class BookKnowledgeAssociationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    book_id: int
    book_title: str
    author: str
    isbn: Optional[str] = None
    category: str
    subjects: List[str] = []
    topics: List[str] = []
    concepts: List[str] = []


class SubjectDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    topics: List[TopicResponse] = []
    associated_books: List[BookKnowledgeAssociationResponse] = []


# ── PILLAR 2: Search-Based Navigation Schemas ─────────────────────────────────

class KnowledgeSearchResult(BaseModel):
    item_type: str  # 'subject', 'topic', 'concept', 'book'
    id: int
    title: str
    description: Optional[str] = None
    relevance_score: float
    explanation: str
    context_path: str  # e.g. "Computer Science > Artificial Intelligence > Machine Learning"
    associated_books_count: int = 0


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[KnowledgeSearchResult]
    total: int


# ── PILLAR 4: Modern AI Comparison Schemas ────────────────────────────────────

class ModelComparisonRequest(BaseModel):
    prompt: str
    models: List[str] = Field(default=["local-deterministic", "gemini-1.5-pro", "gpt-4o"])
    temperature: float = 0.2
    max_tokens: int = 512
    include_rag_context: bool = True


class ModelExecutionResult(BaseModel):
    model_name: str
    provider: str
    response_text: str
    latency_ms: float
    token_usage: Optional[Dict[str, int]] = None
    factual_grounding_score: float  # 0.0 to 1.0 (overlap with retrieved library knowledge)
    citations_count: int
    error: Optional[str] = None


class ModelComparisonResponse(BaseModel):
    prompt: str
    timestamp: datetime
    rag_context_used: Optional[str] = None
    results: List[ModelExecutionResult]


# ── PILLAR 3 & 5: Enhanced Agentic Copilot & RAG Schemas ──────────────────────

class CopilotToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    execution_time_ms: float = 0.0


class StructuredCitation(BaseModel):
    source_type: str  # 'policy', 'monograph', 'study_space', 'subject'
    title: str
    reference_id: Optional[str] = None
    snippet: str
    url_or_action: Optional[str] = None


class EnhancedCopilotResponse(BaseModel):
    answer: str
    intent: str
    confidence: float
    provider: str
    tool_calls: List[CopilotToolCall] = []
    citations: List[StructuredCitation] = []
    spatial_card: Optional[Dict[str, Any]] = None
    book_cards: List[Dict[str, Any]] = []
    suggested_followups: List[str] = []


class ChatMessageInput(BaseModel):
    role: str = Field(..., description="Role of the message sender: 'user' or 'assistant'")
    content: str = Field(..., min_length=1, max_length=4000, description="Message content")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        role_cleaned = v.strip().lower()
        if role_cleaned not in ("user", "assistant"):
            raise ValueError(f"Role must be 'user' or 'assistant', got '{v}'. 'system' and other roles are rejected.")
        return role_cleaned

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message content cannot be empty or whitespace only.")
        return cleaned


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Patron query")
    conversation_history: Optional[List[ChatMessageInput]] = Field(
        default_factory=list,
        description="Prior conversation history bounded to user and assistant turns (max 6 messages retained)",
    )


# ── Stage 12.14 Schemas: Canonical Feature Completion ────────────────────────

# 1. Course Management & Reading Lists (PORT-03, INTEL-06)
class CourseCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, description="Course code (e.g. CS-301)")
    title: str = Field(..., min_length=2, max_length=255, description="Course title")
    department: str = Field(..., min_length=2, max_length=100, description="Academic department")
    term: str = Field(..., min_length=2, max_length=50, description="Academic term (e.g. Fall 2026)")
    description: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    code: str
    title: str
    department: str
    term: str
    instructor_id: int
    instructor_name: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    reading_list_count: int = 0
    reserves_count: int = 0


class CourseListResponse(BaseModel):
    courses: List[CourseResponse]
    total: int


class ReadingListItemCreateRequest(BaseModel):
    book_id: int
    requirement_type: str = Field(default="required", description="'required', 'recommended', 'supplementary'")
    notes: Optional[str] = None

    @field_validator("requirement_type")
    @classmethod
    def validate_req_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("required", "recommended", "supplementary"):
            raise ValueError("Requirement type must be 'required', 'recommended', or 'supplementary'.")
        return clean


class ReadingListItemResponse(BaseModel):
    id: int
    course_id: int
    book_id: int
    book_title: str
    book_author: Optional[str] = None
    book_isbn: Optional[str] = None
    added_by_id: int
    requirement_type: str
    notes: Optional[str] = None
    created_at: datetime
    available_copies_count: int = 0
    total_copies_count: int = 0


# 2. Course Reserves (CIRC-06)
class CourseReserveCreateRequest(BaseModel):
    copy_id: int
    reserve_type: str = Field(default="2_hour", description="'2_hour' or '24_hour'")
    notes: Optional[str] = None

    @field_validator("reserve_type")
    @classmethod
    def validate_res_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("2_hour", "24_hour"):
            raise ValueError("Reserve type must be '2_hour' or '24_hour'.")
        return clean


class CourseReserveResponse(BaseModel):
    id: int
    course_id: int
    course_code: str
    copy_id: int
    copy_code: str
    book_id: int
    book_title: str
    reserve_type: str
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime


# 3. QR Book Collection (CIRC-03)
class BookCollectionPassResponse(BaseModel):
    hold_id: int
    copy_id: int
    copy_code: str
    book_id: int
    book_title: str
    patron_id: int
    patron_name: str
    token: str
    qr_payload: str
    expires_at: datetime


class BookCollectionVerifyRequest(BaseModel):
    token: str = Field(..., min_length=10, description="Collection pass token string")


class BookCollectionVerifyResponse(BaseModel):
    success: bool
    message: str
    loan_id: int
    book_title: str
    copy_code: str
    patron_name: str
    due_date: date


# 4. Lost & Damaged Processing & Audit History (CIRC-07)
class CopyStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="'available', 'maintenance', 'lost', 'damaged', 'retired'")
    notes: Optional[str] = Field(None, max_length=500, description="Incident details or maintenance reason")

    @field_validator("status")
    @classmethod
    def validate_copy_status(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("available", "maintenance", "lost", "damaged", "retired"):
            raise ValueError("Status must be 'available', 'maintenance', 'lost', 'damaged', or 'retired'.")
        return clean


class InventoryEventResponse(BaseModel):
    id: int
    copy_id: int
    copy_code: Optional[str] = None
    book_title: Optional[str] = None
    auditor_id: int
    auditor_name: Optional[str] = None
    event_type: str
    previous_status: Optional[str] = None
    new_status: str
    notes: Optional[str] = None
    recorded_at: datetime


class InventoryEventListResponse(BaseModel):
    items: List[InventoryEventResponse]
    total: int


# 5. Librarian Intelligence Centre & Snapshot & Inventory Analytics (INTEL-01, INTEL-02, INTEL-04)
class IntelligenceSnapshotResponse(BaseModel):
    timestamp: datetime
    active_loans_count: int
    overdue_loans_count: int
    overdue_rate_pct: float
    total_monographs: int
    total_copies: int
    active_holds_count: int
    active_seat_reservations: int
    active_room_reservations: int
    current_occupancy_pct: float
    peak_occupancy_hour: Optional[int] = None


class InventoryAnalyticsResponse(BaseModel):
    total_monographs: int
    total_physical_copies: int
    available_copies: int
    borrowed_copies: int
    maintenance_copies: int
    lost_copies: int
    damaged_copies: int
    collection_turnover_rate: float
    zero_borrow_titles_count: int
    high_demand_titles_count: int
    total_audit_events_count: int


class CirculationDailyPoint(BaseModel):
    date: str
    issues: int
    returns: int
    renewals: int


class CirculationTrendsResponse(BaseModel):
    points: List[CirculationDailyPoint]
    total_issues: int
    total_returns: int
    period_days: int


# 6. Demand Forecasting (INTEL-03)
class DemandForecastDay(BaseModel):
    date: str
    projected_checkouts: float
    lower_bound: float
    upper_bound: float
    day_of_week: str


class TwoWeekDemandForecastResponse(BaseModel):
    horizon_days: int
    start_date: str
    end_date: str
    projections: List[DemandForecastDay]
    baseline_daily_average: float
    trend_direction: str
    confidence_level: float
    methodology: str


# 7. Acquisition Suggestions & Review Workflow (INTEL-05)
class AcquisitionSuggestion(BaseModel):
    query_text: str
    frequency: int
    first_searched: datetime
    last_searched: datetime


class AcquisitionSuggestionListResponse(BaseModel):
    suggestions: List[AcquisitionSuggestion]
    total_zero_result_queries: int


class AcquisitionRequestCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    author: Optional[str] = Field(None, max_length=255)
    isbn: Optional[str] = Field(None, max_length=20)
    search_query_origin: Optional[str] = None
    notes: Optional[str] = None


class AcquisitionRequestUpdate(BaseModel):
    status: str = Field(..., description="'approved', 'rejected', 'ordered', 'received'")
    reviewer_notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_acq_status(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("approved", "rejected", "ordered", "received"):
            raise ValueError("Status must be 'approved', 'rejected', 'ordered', or 'received'.")
        return clean


class AcquisitionRequestResponse(BaseModel):
    id: int
    suggested_title: str
    suggested_author: Optional[str] = None
    isbn: Optional[str] = None
    search_query_origin: Optional[str] = None
    frequency_score: int
    status: str
    requested_by_id: Optional[int] = None
    reviewed_by_id: Optional[int] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AcquisitionRequestListResponse(BaseModel):
    items: List[AcquisitionRequestResponse]
    total: int





