"""Deterministic synthetic user generator for AI Library Management System.

Generates:
- 500 Students
- 25 Teachers
- 5 Librarians
Total = 530 Users.

Each account receives a unique bcrypt salt. Credentials are explicitly documented
as synthetic demo credentials.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import bcrypt

from app.seed_data.generator import SeederConfig, get_namespace_rng
from app.seed_data.vocabulary import FIRST_NAMES, LAST_NAMES, DEPARTMENTS

# Standard synthetic demonstration credentials
DEMO_PASSWORDS: Dict[str, str] = {
    "student": "StudentSecret123!",
    "teacher": "TeacherSecret123!",
    "librarian": "LibrarianSecret123!",
}


@dataclass
class SyntheticUser:
    id: int
    email: str
    full_name: str
    hashed_password: str
    role: str
    is_active: bool
    created_at: datetime
    department: Optional[str] = None


def generate_users(config: SeederConfig, bcrypt_rounds: int = 8) -> List[SyntheticUser]:
    """
    Generates exactly 530 users:
    - 5 Librarians (IDs 1..5)
    - 25 Teachers (IDs 6..30)
    - 500 Students (IDs 31..530)
    """
    rng = get_namespace_rng(config.base_seed, "users")
    users: List[SyntheticUser] = []
    used_emails = set()

    current_id = 1

    # ── 1. 5 Librarians ───────────────────────────────────────────────────────
    librarian_specs = [
        ("Chief Librarian", "chief.librarian@university.edu"),
        ("Senior Acquisitions Librarian", "acquisitions.librarian@university.edu"),
        ("Circulation Desk Head", "circulation.librarian@university.edu"),
        ("Digital Archives Specialist", "archives.librarian@university.edu"),
        ("Research Services Librarian", "research.librarian@university.edu"),
    ]
    for name, email in librarian_specs:
        salt = bcrypt.gensalt(rounds=bcrypt_rounds)
        hashed = bcrypt.hashpw(DEMO_PASSWORDS["librarian"].encode("utf-8"), salt).decode("utf-8")
        created_dt = config.as_of - timedelta(days=rng.randint(300, 365))
        users.append(
            SyntheticUser(
                id=current_id,
                email=email,
                full_name=name,
                hashed_password=hashed,
                role="librarian",
                is_active=True,
                created_at=created_dt,
                department="University Library",
            )
        )
        used_emails.add(email)
        current_id += 1

    # ── 2. 25 Teachers ────────────────────────────────────────────────────────
    for i in range(25):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        dept = rng.choice(DEPARTMENTS)
        full_name = f"Professor {first} {last}"
        
        email_candidate = f"prof.{last.lower()}{i+1}@university.edu".replace(" ", "").replace("-", "")
        salt = bcrypt.gensalt(rounds=bcrypt_rounds)
        hashed = bcrypt.hashpw(DEMO_PASSWORDS["teacher"].encode("utf-8"), salt).decode("utf-8")
        created_dt = config.as_of - timedelta(days=rng.randint(180, 330))
        users.append(
            SyntheticUser(
                id=current_id,
                email=email_candidate,
                full_name=full_name,
                hashed_password=hashed,
                role="teacher",
                is_active=True,
                created_at=created_dt,
                department=dept,
            )
        )
        used_emails.add(email_candidate)
        current_id += 1

    # ── 3. 500 Students ───────────────────────────────────────────────────────
    for i in range(500):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        dept = rng.choice(DEPARTMENTS)
        full_name = f"{first} {last}"

        clean_first = first.lower().replace(" ", "").replace("-", "")
        clean_last = last.lower().replace(" ", "").replace("-", "")
        email_candidate = f"student.{clean_first}.{clean_last}{i+1}@university.edu"
        
        salt = bcrypt.gensalt(rounds=bcrypt_rounds)
        hashed = bcrypt.hashpw(DEMO_PASSWORDS["student"].encode("utf-8"), salt).decode("utf-8")
        created_dt = config.as_of - timedelta(days=rng.randint(30, 240))
        users.append(
            SyntheticUser(
                id=current_id,
                email=email_candidate,
                full_name=full_name,
                hashed_password=hashed,
                role="student",
                is_active=True,
                created_at=created_dt,
                department=dept,
            )
        )
        used_emails.add(email_candidate)
        current_id += 1

    return users

