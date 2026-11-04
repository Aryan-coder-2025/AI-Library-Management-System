"""
Idempotent development-only demonstration dataset seeder for AI Library Management System.
Populates realistic fictional books, physical inventory copies, demo accounts,
circulation loans, and vector embeddings.
"""
from datetime import date, datetime, timedelta
import os
import sys
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal, atomic_write, init_db
from app.models import Book, BookCopy, Loan, User
from app.schemas import validate_isbn_string
from app.services.semantic import refresh_embeddings_service

# Plausible demonstration monographs covering key academic/technology domains
DEMO_BOOKS = [
    {
        "title": "Designing Distributed Microservices and Event Meshes",
        "author": "Elena Rostova",
        "category": "Computer Science",
        "isbn": "9780134685991",
        "description": "Architectural principles for high-throughput distributed systems, event-driven streaming pipelines, consensus protocols, and fault-tolerant service meshes.",
        "copies": [
            {"copy_code": "CS-DIST-001", "status": "available", "notes": "Main Stack, Level 2"},
            {"copy_code": "CS-DIST-002", "status": "available", "notes": "Reserve Desk"},
        ],
    },
    {
        "title": "Database Internals: Storage Engines and Query Optimization",
        "author": "Arthur Pendelton",
        "category": "Computer Science",
        "isbn": "9781491950357",
        "description": "Comprehensive dive into B-Trees, LSM trees, write-ahead logging, MVCC concurrency controls, and cost-based SQL relational query execution planners.",
        "copies": [
            {"copy_code": "CS-DB-001", "status": "available", "notes": "Main Stack, Level 2"},
            {"copy_code": "CS-DB-002", "status": "maintenance", "notes": "Binding inspection"},
        ],
    },
    {
        "title": "Compilers and Virtual Machines: Theory to Native Code",
        "author": "Dr. Marcus Vance",
        "category": "Computer Science",
        "isbn": "9780201100884",
        "description": "Lexical analysis, abstract syntax trees, SSA intermediate representations, register allocation algorithms, and JIT compilation techniques.",
        "copies": [
            {"copy_code": "CS-COMP-001", "status": "available", "notes": "Main Stack, Level 2"},
            {"copy_code": "CS-COMP-002", "status": "available", "notes": "Study Room 3"},
        ],
    },
    {
        "title": "Foundations of Deep Learning and Neural Architectures",
        "author": "Dr. Siobhan Wu",
        "category": "Artificial Intelligence",
        "isbn": "9780262035613",
        "description": "Mathematical formulations of backpropagation, convolutional representations, residual connections, attention mechanisms, and gradient descent optimization.",
        "copies": [
            {"copy_code": "AI-DL-001", "status": "available", "notes": "AI Lab Shelf A"},
            {"copy_code": "AI-DL-002", "status": "available", "notes": "AI Lab Shelf A"},
            {"copy_code": "AI-DL-003", "status": "available", "notes": "Reference collection"},
        ],
    },
    {
        "title": "Reinforcement Learning and Autonomous Decision Systems",
        "author": "Tariq Al-Mansoor",
        "category": "Artificial Intelligence",
        "isbn": "9780262039246",
        "description": "Markov decision processes, dynamic programming, temporal-difference learning, Q-learning, policy gradients, actor-critic methods, and multi-agent coordination.",
        "copies": [
            {"copy_code": "AI-RL-001", "status": "available", "notes": "Robotics Center"},
            {"copy_code": "AI-RL-002", "status": "available", "notes": "Main Stack, Level 3"},
        ],
    },
    {
        "title": "Natural Language Processing with Transformers",
        "author": "Priya Sharma & Liam Scott",
        "category": "Artificial Intelligence",
        "isbn": "9781098103248",
        "description": "Self-attention mechanisms, encoder-decoder architectures, pretraining objectives, tokenization pipelines, instruction tuning, and semantic vector embeddings.",
        "copies": [
            {"copy_code": "AI-NLP-001", "status": "available", "notes": "Language Lab"},
            {"copy_code": "AI-NLP-002", "status": "available", "notes": "Main Stack, Level 3"},
        ],
    },
    {
        "title": "Computer Vision: Algorithms, Geometry, and Deep Representations",
        "author": "Hiroshi Tanaka",
        "category": "Artificial Intelligence",
        "isbn": "9780387314396",
        "description": "Epipolar geometry, optical flow, point cloud processing, convolutional object detectors, vision transformers, and neural radiance fields.",
        "copies": [
            {"copy_code": "AI-CV-001", "status": "available", "notes": "Media Center"},
            {"copy_code": "AI-CV-002", "status": "available", "notes": "Main Stack, Level 3"},
        ],
    },
    {
        "title": "Advanced Linear Algebra and Spectral Methods",
        "author": "Prof. Clara Montgomery",
        "category": "Mathematics",
        "isbn": "9780387982588",
        "description": "Vector spaces, singular value decomposition, eigenvalue problems, Jordan canonical forms, spectral theorem, and matrix factorizations for high-dimensional data.",
        "copies": [
            {"copy_code": "MATH-LA-001", "status": "available", "notes": "Math Annex"},
            {"copy_code": "MATH-LA-002", "status": "available", "notes": "Main Stack, Level 1"},
        ],
    },
    {
        "title": "Probability Theory and Stochastic Processes for Engineering",
        "author": "Julian Becker",
        "category": "Mathematics",
        "isbn": "9780521546904",
        "description": "Measure-theoretic probability foundations, random walks, Poisson processes, continuous-time Markov chains, and martingale convergence theorems.",
        "copies": [
            {"copy_code": "MATH-STOCH-001", "status": "available", "notes": "Math Annex"},
            {"copy_code": "MATH-STOCH-002", "status": "available", "notes": "Main Stack, Level 1"},
        ],
    },
    {
        "title": "Numerical Optimization and Convex Analysis",
        "author": "Sofia Chen",
        "category": "Mathematics",
        "isbn": "9780387303031",
        "description": "Unconstrained and constrained convex optimization, KKT conditions, interior-point methods, proximal gradient algorithms, and Lagrangian duality.",
        "copies": [
            {"copy_code": "MATH-OPT-001", "status": "available", "notes": "Math Annex"},
            {"copy_code": "MATH-OPT-002", "status": "available", "notes": "Main Stack, Level 1"},
        ],
    },
    {
        "title": "Principles of Quantum Computing and Information Theory",
        "author": "Dr. Alistair Finch",
        "category": "Physics",
        "isbn": "9780521635035",
        "description": "Qubits, quantum superposition, entanglement, Grover search algorithm, Shor factoring, quantum error-correcting codes, and decoherence models.",
        "copies": [
            {"copy_code": "PHYS-QC-001", "status": "available", "notes": "Physics Department"},
            {"copy_code": "PHYS-QC-002", "status": "available", "notes": "Main Stack, Level 4"},
        ],
    },
    {
        "title": "Statistical Mechanics and Thermodynamic Fluctuation Theory",
        "author": "Henrik Lindqvist",
        "category": "Physics",
        "isbn": "9780198517948",
        "description": "Microcanonical and grand canonical ensembles, Bose-Einstein and Fermi-Dirac statistics, phase transitions, critical phenomena, and non-equilibrium dynamics.",
        "copies": [
            {"copy_code": "PHYS-STAT-001", "status": "available", "notes": "Physics Department"},
            {"copy_code": "PHYS-STAT-002", "status": "available", "notes": "Main Stack, Level 4"},
        ],
    },
    {
        "title": "Practical Cryptography and Protocol Verification",
        "author": "Naomi Vance",
        "category": "Cybersecurity",
        "isbn": "9780470479520",
        "description": "Symmetric primitives, elliptic curve cryptography, authenticated key exchanges, post-quantum signatures, zero-knowledge proofs, and automated protocol verification.",
        "copies": [
            {"copy_code": "SEC-CRYPTO-001", "status": "available", "notes": "Security Lab"},
            {"copy_code": "SEC-CRYPTO-002", "status": "available", "notes": "Security Lab"},
        ],
    },
    {
        "title": "Zero Trust Architecture and Cloud Security",
        "author": "David Sterling",
        "category": "Cybersecurity",
        "isbn": "9781492080336",
        "description": "Identity-aware access proxies, mutual TLS micro-segmentation, ephemeral credentials, container hardening, and threat detection in cloud infrastructure.",
        "copies": [
            {"copy_code": "SEC-ZT-001", "status": "available", "notes": "Security Lab"},
            {"copy_code": "SEC-ZT-002", "status": "available", "notes": "Main Stack, Level 2"},
        ],
    },
    {
        "title": "Ethics of Artificial Intelligence and Automated Governance",
        "author": "Maya Lin",
        "category": "General Technology",
        "isbn": "9780190905033",
        "description": "Algorithmic bias, explainability standards, autonomous accountability frameworks, data governance policies, and societal impacts of generative AI.",
        "copies": [
            {"copy_code": "GEN-ETHICS-001", "status": "available", "notes": "Reading Room East"},
            {"copy_code": "GEN-ETHICS-002", "status": "available", "notes": "Main Stack, Level 1"},
        ],
    },
]


def seed_demo_users(db: Session) -> Dict[str, str]:
    """Ensures standard demonstration student and librarian accounts exist."""
    with atomic_write(db):
        student = db.execute(select(User).where(User.email == "demo_student@library.local")).scalar_one_or_none()
        if not student:
            student = User(
                email="demo_student@library.local",
                full_name="Demo Student Patron",
                hashed_password=hash_password(os.environ.get("DEMO_STUDENT_PASSWORD", "StudentDemo123!")),
                role="student",
                is_active=True,
            )
            db.add(student)
            db.flush()

        librarian = db.execute(select(User).where(User.email == "demo_librarian@library.local")).scalar_one_or_none()
        if not librarian:
            librarian = User(
                email="demo_librarian@library.local",
                full_name="Demo Staff Librarian",
                hashed_password=hash_password(os.environ.get("DEMO_LIBRARIAN_PASSWORD", "LibrarianDemo123!")),
                role="librarian",
                is_active=True,
            )
            db.add(librarian)
            db.flush()

    return {
        "student": "demo_student@library.local",
        "librarian": "demo_librarian@library.local",
    }


def seed_demo_catalogue(db: Session) -> int:
    """Idempotently seeds demonstration books and physical copies."""
    count = 0
    with atomic_write(db):
        for item in DEMO_BOOKS:
            clean_isbn = validate_isbn_string(item["isbn"])
            book = db.execute(select(Book).where(Book.isbn == clean_isbn)).scalar_one_or_none()

            if not book:
                book = Book(
                    title=item["title"],
                    author=item["author"],
                    category=item["category"],
                    isbn=clean_isbn,
                    description=item["description"],
                    is_archived=False,
                )
                db.add(book)
                db.flush()

            # Ensure copies exist
            for copy_spec in item["copies"]:
                existing_copy = db.execute(
                    select(BookCopy).where(BookCopy.copy_code == copy_spec["copy_code"])
                ).scalar_one_or_none()

                if not existing_copy:
                    copy = BookCopy(
                        book_id=book.id,
                        copy_code=copy_spec["copy_code"],
                        operational_status=copy_spec["status"],
                        notes=copy_spec.get("notes"),
                    )
                    db.add(copy)
                    db.flush()

            count += 1

    return count


def seed_demo_loans(db: Session, student_email: str, librarian_email: str) -> None:
    """Sets up demonstration loans safely adhering to Stage 4 circulation rules."""
    with atomic_write(db):
        student = db.execute(select(User).where(User.email == student_email)).scalar_one_or_none()
        librarian = db.execute(select(User).where(User.email == librarian_email)).scalar_one_or_none()
        if not student or not librarian:
            return

        # Check copy CS-DIST-001
        copy1 = db.execute(
            select(BookCopy).where(BookCopy.copy_code == "CS-DIST-001")
        ).scalar_one_or_none()

        if copy1:
            existing_loan1 = db.execute(
                select(Loan).where(Loan.copy_id == copy1.id, Loan.returned_at.is_(None))
            ).scalar_one_or_none()

            if not existing_loan1:
                today = date.today()
                loan1 = Loan(
                    student_id=student.id,
                    copy_id=copy1.id,
                    issued_by_id=librarian.id,
                    issued_at=datetime.utcnow() - timedelta(days=2),
                    due_date=today + timedelta(days=12),
                    returned_at=None,
                )
                db.add(loan1)
                db.flush()

        # Create one returned historical loan for "Foundations of Deep Learning" copy AI-DL-003
        copy2 = db.execute(
            select(BookCopy).where(BookCopy.copy_code == "AI-DL-003")
        ).scalar_one_or_none()

        if copy2:
            existing_loan2 = db.execute(
                select(Loan).where(Loan.copy_id == copy2.id)
            ).scalar_one_or_none()

            if not existing_loan2:
                loan2 = Loan(
                    student_id=student.id,
                    copy_id=copy2.id,
                    issued_by_id=librarian.id,
                    issued_at=datetime.utcnow() - timedelta(days=20),
                    due_date=date.today() - timedelta(days=6),
                    returned_at=datetime.utcnow() - timedelta(days=7),
                )
                db.add(loan2)
                db.flush()


def run_seed():
    """Main execution function for demonstration data population."""
    init_db()

    print("[1/4] Ensuring demonstration accounts...")
    with SessionLocal() as db:
        user_emails = seed_demo_users(db)
        print(f"      Student:   {user_emails['student']}")
        print(f"      Librarian: {user_emails['librarian']}")

    print("[2/4] Seeding catalogue monographs and physical copies...")
    with SessionLocal() as db:
        book_count = seed_demo_catalogue(db)
        print(f"      Verified {book_count} titles in catalogue.")

    print("[3/4] Establishing realistic circulation loans...")
    with SessionLocal() as db:
        seed_demo_loans(db, user_emails["student"], user_emails["librarian"])
        print("      Circulation loans configured (1 active, 1 returned).")

    print("[4/4] Generating AI vector embeddings for catalogue...")
    with SessionLocal() as db:
        db.info["_in_atomic_write"] = True
        try:
            res = refresh_embeddings_service(db, force_refresh=False)
            db.commit()
            print(f"      Embedding Status: {res.status}")
            print(f"      Processed: {res.processed}, Total Candidates: {res.total_candidates}")
        except Exception as e:
            db.rollback()
            print(f"      Notice: Vector embedding step reported: {e}")

    print("\n=== DEMO SEED COMPLETED SUCCESSFULLY ===")


def inspect_database():
    """Inspects and reports summary statistics of current database state."""
    init_db()
    with SessionLocal() as db:
        total_users = db.query(User).count()
        students = db.query(User).filter(User.role == "student").count()
        librarians = db.query(User).filter(User.role == "librarian").count()
        total_books = db.query(Book).count()
        total_copies = db.query(BookCopy).count()
        available_copies = db.query(BookCopy).filter(BookCopy.operational_status == "available").count()
        active_loans = db.query(Loan).filter(Loan.returned_at.is_(None)).count()
        returned_loans = db.query(Loan).filter(Loan.returned_at.isnot(None)).count()
        embedded_books = db.query(Book).filter(Book.embedding.isnot(None)).count()

        print("\n=== LIBRARY DATABASE SUMMARY ===")
        print(f"Total Users:        {total_users} ({students} students, {librarians} librarians)")
        print(f"Total Books:        {total_books}")
        print(f"Total Copies:       {total_copies} ({available_copies} available operational status)")
        print(f"Circulation Loans:  {active_loans} active, {returned_loans} returned")
        print(f"AI Vector Coverage: {embedded_books} / {total_books} books embedded")
        print("================================\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--inspect", "--status"):
        inspect_database()
    else:
        run_seed()
        inspect_database()
