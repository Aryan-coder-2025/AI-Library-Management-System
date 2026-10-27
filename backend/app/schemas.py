from datetime import datetime, date
import re
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
