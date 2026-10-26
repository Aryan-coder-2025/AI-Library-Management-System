from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    Index,
    Text,
    LargeBinary
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'student' or 'librarian'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    loans = relationship("Loan", back_populates="student", foreign_keys="Loan.student_id")
    issued_loans = relationship("Loan", back_populates="issued_by", foreign_keys="Loan.issued_by_id")


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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    copies = relationship("BookCopy", back_populates="book", cascade="all, delete-orphan", passive_deletes=True)


class BookCopy(Base):
    __tablename__ = "book_copies"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False, index=True)
    copy_code = Column(String(50), unique=True, nullable=False, index=True)
    
    # Physical status: 'available', 'maintenance', 'lost'
    # 'borrowed' is strictly derived from active loans and never stored here
    operational_status = Column(String(20), default="available", nullable=False)
    notes = Column(Text, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    book = relationship("Book", back_populates="copies")
    loans = relationship("Loan", back_populates="copy")


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
