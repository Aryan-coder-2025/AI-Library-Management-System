# Database Schema & Data Integrity Reference

**Document Version:** 1.0.0  
**Database Engine:** SQLite 3 (WAL Mode)  
**ORM:** SQLAlchemy 2.1.6  
**Migration Tool:** Alembic 1.20.1  
**Default Database Path:** `backend/library.db`  

---

## 1. Database Configuration & Path Resolution

### Database Files and Baseline Integrity
The repository manages three distinct SQLite database files, with cryptographic baselines documented in [database-integrity.md](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/docs/database-integrity.md):
1. `backend/library.db` (**Protected Development Database**):
   - Contains the initial development catalogue (15 monographs, 31 physical barcode copies, 2 circulation loans, 4 user accounts, and 15 precomputed 384-dimensional vector embeddings).
   - Maintained strictly at Alembic revision `0f610073e5f1` (SHA-256: `3bd0578347ba99313fd3640669d80f66d6858ecb484a9741b206550ab906fab8`). Protected against automatic migration upgrades.
2. `library.db` (**Protected Legacy Root Database**):
   - An empty, migrated database schema (0 rows in all data tables).
   - Preserved as a clean historical baseline at revision `0f610073e5f1` (SHA-256: `fd764e0b0b5eda1ab0abe932055ee8b2d0e843001571f169760f9d32850d7931`).
3. `backend/library_demo.db` (**Published Demo Database**):
   - Contains the 60,199-record synthetic demonstration dataset generated in Phase 1 (1,500 monographs, 4,000 copies, 530 users, 10,000 loans, 3,000 reservations, 41,000 telemetry events).
   - Head schema revision `c3d4e5f6a7b8` (SHA-256: `df59eba1c765457e5129b5be08917bc4049d7ff250ea4aa080010ad9655c3bd3`). Protected as read-only.

### Path Resolution Hardening (Phase 0 Step 2)
In [`backend/app/config.py`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/app/config.py), the default database URL is anchored deterministically to the location of the `backend/` directory:
```python
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = (BACKEND_DIR / "library.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
```
- **Working Directory Independence:** Launching the backend from the repository root (`uvicorn backend.app.main:app`), from the `backend/` directory (`uvicorn app.main:app`), or from a task runner automatically targets `backend/library.db`.
- **Precedence Rule:** An explicitly supplied `DATABASE_URL` (such as `sqlite:///:memory:` in unit test fixtures) overrides the default.

---

## 2. SQLite Pragmas & Concurrency Model

Connection configuration in [`backend/app/database.py`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/app/database.py#L19-L55) enforces:
- `PRAGMA foreign_keys = ON;`: Enforces referential integrity constraints across foreign keys at the SQLite engine level.
- `PRAGMA busy_timeout = 5000;`: Waits up to 5,000 ms on locked tables before raising an operational error.
- `PRAGMA journal_mode = WAL;`: Set at startup using a standalone connection without an active transaction block. Allows concurrent readers to access records while a writer holds an active transaction.
- `BEGIN IMMEDIATE` (Upfront Write Locking): For state-changing transactions ([`atomic_write`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/app/database.py#L113) and `get_write_db`), SQLite acquires the reserved write lock immediately before performing any reads, eliminating Time-of-Check to Time-of-Use (TOCTOU) race conditions during concurrent book checkouts.

---

## 3. Schema Definitions & Table Reference

### Table: `users`
Stores student and staff credentials, account roles, and status flags.

| Column | Type | Nullable | Primary Key | Default | Constraints / Index | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | No | Yes | Auto-increment | Index `ix_users_id` | Unique user account identifier |
| `email` | `VARCHAR(255)` | No | No | — | Unique Index `ix_users_email` | Case-normalized login email |
| `hashed_password` | `VARCHAR(255)` | No | No | — | — | Bcrypt-hashed password string (12 rounds) |
| `full_name` | `VARCHAR(255)` | No | No | — | — | Display and legal name |
| `role` | `VARCHAR(50)` | No | No | — | Value in `('student', 'librarian')` | Access control role |
| `is_active` | `BOOLEAN` | No | No | `True` | — | Account enablement status |
| `created_at` | `DATETIME` | No | No | `utcnow` | — | Account registration timestamp |

**ORM Relationships:**
- `loans`: Relationship to `Loan` where `Loan.student_id == User.id`.
- `issued_loans`: Relationship to `Loan` where `Loan.issued_by_id == User.id`.

---

### Table: `books`
Stores bibliographic records for monographs catalogued in the library collection.

| Column | Type | Nullable | Primary Key | Default | Constraints / Index | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | No | Yes | Auto-increment | Index `ix_books_id` | Unique book record identifier |
| `title` | `VARCHAR(255)` | No | No | — | Index `ix_books_title` | Monograph title |
| `author` | `VARCHAR(255)` | No | No | — | Index `ix_books_author` | Author full name |
| `isbn` | `VARCHAR(30)` | Yes | No | `NULL` | Unique `uq_books_isbn` | Validated ISBN-10 or ISBN-13 |
| `category` | `VARCHAR(100)` | No | No | — | Index `ix_books_category` | Academic subject or genre |
| `description` | `TEXT` | Yes | No | `NULL` | — | Synopsis or abstract |
| `is_archived` | `BOOLEAN` | No | No | `False` | Index `ix_books_is_archived` | Soft-deletion flag |
| `embedding` | `BLOB` (`LargeBinary`) | Yes | No | `NULL` | — | 384-dimensional `float32` vector (1,536 bytes) |
| `embedding_updated_at` | `DATETIME` | Yes | No | `NULL` | — | Timestamp of last vector generation |
| `created_at` | `DATETIME` | No | No | `utcnow` | — | Monograph creation timestamp |
| `updated_at` | `DATETIME` | No | No | `utcnow` | — | Metadata update timestamp |

**ORM Hooks & Rules:**
- [`_book_before_update`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/app/models.py#L57-L70): SQLAlchemy event listener that advances `updated_at` only when core bibliographic fields change (`title`, `author`, `isbn`, `category`, `description`, `is_archived`). It does *not* advance `updated_at` when updating `embedding` vectors, preventing vector refresh loops.
- **ORM Relationships:**
  - `copies`: Relationship to `BookCopy` with `cascade="all, delete-orphan", passive_deletes=True`.

---

### Table: `book_copies`
Represents individual physical inventory items associated with a catalogued monograph.

| Column | Type | Nullable | Primary Key | Default | Constraints / Index | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | No | Yes | Auto-increment | Index `ix_book_copies_id` | Physical copy identifier |
| `book_id` | `INTEGER` | No | No | — | Foreign Key `books.id` (`ON DELETE RESTRICT`), Index `ix_book_copies_book_id` | Parent monograph reference |
| `copy_code` | `VARCHAR(50)` | No | No | — | Unique Index `ix_book_copies_copy_code` | Physical barcode / accession code |
| `operational_status` | `VARCHAR(20)` | No | No | `"available"` | Value in `('available', 'maintenance', 'lost', 'retired')` | Physical status of item |
| `notes` | `TEXT` | Yes | No | `NULL` | — | Shelf location, condition, or edition |
| `added_at` | `DATETIME` | No | No | `utcnow` | — | Copy registration timestamp |

**Integrity Rule:**
- **No Stored "Borrowed" State:** `operational_status` *never* stores `"borrowed"`. Borrowed state is dynamically computed from the active presence of an unreturned `loans` record (`Loan.returned_at IS NULL`).

---

### Table: `loans`
Maintains the circulation desk history of physical book borrowings and returns.

| Column | Type | Nullable | Primary Key | Default | Constraints / Index | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | No | Yes | Auto-increment | Index `ix_loans_id` | Unique loan transaction identifier |
| `student_id` | `INTEGER` | No | No | — | Foreign Key `users.id` (`ON DELETE RESTRICT`), Index `ix_loans_student_id` | Borrower user ID |
| `copy_id` | `INTEGER` | No | No | — | Foreign Key `book_copies.id` (`ON DELETE RESTRICT`), Index `ix_loans_copy_id` | Borrowed physical copy ID |
| `issued_by_id` | `INTEGER` | No | No | — | Foreign Key `users.id` (`ON DELETE RESTRICT`) | Staff librarian user ID |
| `issued_at` | `DATETIME` | No | No | `utcnow` | — | Loan check-out timestamp |
| `due_date` | `DATE` | No | No | — | Index `ix_loans_due_date` | Calculated due date (issued_at + 14 days student, + 30 days teacher) |
| `returned_at` | `DATETIME` | Yes | No | `NULL` | Index `ix_loans_returned_at` | Return timestamp (`NULL` indicates active loan) |
| `renewal_count` | `INTEGER` | No | No | `0` | — | Total count of self-service/staff due date extensions (max 1 renewal) |

**Partial Unique Index:**
- `uix_one_active_loan_per_copy`:
  ```sql
  CREATE UNIQUE INDEX uix_one_active_loan_per_copy ON loans (copy_id) WHERE returned_at IS NULL;
  ```
  Guarantees at the database engine level that no physical copy can have more than one concurrent unreturned loan, preventing double-checkout anomalies.


---

### Table: `notifications`
Maintains patron in-app alerts and overdue warning notifications (CIRC-04).

| Column | Type | Nullable | Primary Key | Default | Constraints / Index | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | No | Yes | Auto-increment | Index `ix_notifications_id` | Unique notification identifier |
| `user_id` | `INTEGER` | No | No | — | Foreign Key `users.id` (`ON DELETE CASCADE`), Index `ix_notifications_user_id` | Recipient patron user ID |
| `loan_id` | `INTEGER` | Yes | No | `NULL` | Foreign Key `loans.id` (`ON DELETE SET NULL`), Index `ix_notifications_loan_id` | Associated overdue loan ID |
| `notification_type` | `VARCHAR(50)` | No | No | `"overdue"` | Index `ix_notifications_notification_type` | Category of alert (`"overdue"`, `"general"`) |
| `title` | `VARCHAR(200)` | No | No | — | — | Brief notification headline |
| `message` | `TEXT` | No | No | — | — | Formatted notice body explaining days overdue |
| `target_due_date` | `DATE` | Yes | No | `NULL` | — | Original or extended due date referenced by alert |
| `is_read` | `BOOLEAN` | No | No | `False` | Index `ix_notifications_is_read` | Read acknowledgment state |
| `dedup_key` | `VARCHAR(100)` | No | No | — | Unique Index `ix_notifications_dedup_key` | Deterministic key `overdue:{loan_id}:{due_date}` ensuring sweep idempotency |
| `created_at` | `DATETIME` | No | No | `utcnow` | — | Notification creation timestamp |
| `read_at` | `DATETIME` | Yes | No | `NULL` | — | Timestamp when patron marked alert as read |


---

## 4. Alembic Migrations

All tables, indexes, and constraints are managed via sequential Alembic migrations:
- `0f610073e5f1` (**Initial Schema**): Core relational baseline (`users`, `books`, `book_copies`, `loans`).
- `b2c3d4e5f6a7` (**Phase 1 Resource Management**): Spatial models (`study_zones`, `study_seats`, `study_rooms`, `reservations`, telemetry events, and exclusion triggers).
- `c3d4e5f6a7b8` (**Align Reservation Triggers**): Corrective migration narrowing reservation conflict triggers to `status = 'active'`.
- `d4e5f6a7b8c9` (**Patron Self-Service & Notifications - HEAD**): Adds `loans.renewal_count` and creates `notifications` table with unique constraint on `dedup_key`.

- **Idempotent Application:** [`init_db()`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/app/database.py#L188) automatically runs `alembic upgrade head` on unmigrated non-protected databases, safely verifying that the schema matches the ORM model definitions.

