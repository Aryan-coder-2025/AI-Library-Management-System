import argparse
import getpass
import os
import re
import sys
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal, atomic_write, init_db
from app.models import User

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


def validate_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError(f"Invalid email format: '{email}'")
    return cleaned


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    return password


def create_librarian_account(
    email: str,
    full_name: str,
    password: str,
    initial_only: bool = False,
    confirm_additional: bool = False,
    interactive: bool = False,
    db_session: Optional[Session] = None,
) -> User:
    """
    Creates a librarian account in the database.
    - Rejects duplicate email.
    - If initial_only is True, fails if any librarian already exists.
    - If a librarian exists and confirm_additional is False, requires explicit confirmation
      (interactive prompt or --confirm-additional flag).
    - Hashes the password securely via bcrypt.
    """
    clean_email = validate_email(email)
    clean_name = full_name.strip()
    if not clean_name:
        raise ValueError("Full name cannot be empty.")
    validate_password(password)

    def _execute_creation(session: Session) -> User:
        # If interactive and confirmation not pre-granted, check if prompt is needed BEFORE acquiring write lock
        if interactive and not confirm_additional:
            existing_librarian = session.execute(
                select(User).where(User.role == "librarian")
            ).first()
            # Rollback query transaction to leave session clean for atomic_write
            session.rollback()

            if existing_librarian:
                if initial_only:
                    raise ValueError("A librarian account already exists and --initial-only was specified.")
                confirm = input("Notice: A librarian account already exists. Create another librarian? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes"):
                    raise ValueError("Operation cancelled by user.")

        with atomic_write(session):
            # 1. Atomic check if email is already taken
            existing_user = session.execute(
                select(User).where(User.email == clean_email)
            ).scalar_one_or_none()
            if existing_user:
                raise ValueError(f"A user with email '{clean_email}' already exists.")

            # 2. Atomic check for librarian existence and confirmation rules
            existing_librarian = session.execute(
                select(User).where(User.role == "librarian")
            ).first()
            if existing_librarian:
                if initial_only:
                    raise ValueError("A librarian account already exists and --initial-only was specified.")
                if not confirm_additional and not interactive:
                    raise ValueError(
                        "A librarian account already exists. Creating additional librarian accounts requires explicit confirmation (e.g. --confirm-additional)."
                    )

            # 3. Create librarian record
            new_librarian = User(
                email=clean_email,
                full_name=clean_name,
                hashed_password=hash_password(password),
                role="librarian",
                is_active=True,
            )
            session.add(new_librarian)
            session.flush()

            return new_librarian

    if db_session is not None:
        return _execute_creation(db_session)
    else:
        init_db()
        with SessionLocal() as session:
            librarian = _execute_creation(session)
            librarian_id = librarian.id
        with SessionLocal() as session:
            return session.get(User, librarian_id)


def main():
    parser = argparse.ArgumentParser(
        description="Secure CLI for bootstrapping librarian accounts in the AI Library Management System."
    )
    parser.add_argument("--email", help="Librarian email address", default=None)
    parser.add_argument("--full-name", help="Librarian full name", default=None)
    parser.add_argument("--initial-only", action="store_true", help="Only permit creation if no librarian exists yet")
    parser.add_argument(
        "--confirm-additional",
        action="store_true",
        help="Explicitly confirm creation of an additional librarian account when one already exists",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without interactive prompts (fails if required inputs or confirmations are missing)",
    )

    args = parser.parse_args()

    is_interactive = not args.non_interactive

    email = args.email
    if not email:
        if not is_interactive:
            print("Error: --email is required in non-interactive mode.", file=sys.stderr)
            sys.exit(1)
        email = input("Enter librarian email: ").strip()

    full_name = args.full_name
    if not full_name:
        if not is_interactive:
            print("Error: --full-name is required in non-interactive mode.", file=sys.stderr)
            sys.exit(1)
        full_name = input("Enter librarian full name: ").strip()

    # Passwords should not be passed through command-line arguments to avoid leaking secrets
    # in process lists (ps/tasklist), shell history, or terminal logs.
    # We use a secure interactive prompt via getpass, with support for the
    # LIBRARIAN_BOOTSTRAP_PASSWORD environment variable for automated environments.
    password = os.environ.get("LIBRARIAN_BOOTSTRAP_PASSWORD")
    if not password:
        if not is_interactive:
            print(
                "Error: Password must be provided via LIBRARIAN_BOOTSTRAP_PASSWORD in non-interactive mode.",
                file=sys.stderr,
            )
            sys.exit(1)
        password = getpass.getpass("Enter librarian password: ")
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    try:
        librarian = create_librarian_account(
            email=email,
            full_name=full_name,
            password=password,
            initial_only=args.initial_only,
            confirm_additional=args.confirm_additional,
            interactive=is_interactive,
        )
        print(f"Librarian account successfully created for '{librarian.email}' (ID: {librarian.id}).")
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
