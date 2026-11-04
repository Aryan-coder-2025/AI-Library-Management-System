# API Reference

**Document Version:** 1.0.0  
**Base URL:** `http://localhost:8000` (or `http://127.0.0.1:8000`)  
**Frontend Proxy:** Vite proxies all `/api/*` calls from `http://localhost:5173` to `http://127.0.0.1:8000`.

---

## 1. Authentication & Security Conventions

### Cookie-Based Session
- **Authentication Token:** Stored in an `HttpOnly` cookie named `access_token` (`SameSite=Lax`, `Path=/`).
- **CSRF Token:** Non-HttpOnly cookie named `csrf_token` (`SameSite=Lax`, `Path=/`).
- **CSRF Header:** State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) must supply `X-CSRF-Token: <token>` matching the `csrf_token` cookie value.
- **Origin Validation:** The `Origin` header must match `ALLOWED_ORIGINS` (`http://localhost:5173`, `http://127.0.0.1:5173`).

### Role-Based Access Control (RBAC)
- **Public / Unauthenticated:** Endpoints that do not require an active session.
- **Active User (`student` or `librarian`):** Endpoints requiring an authenticated, active account (`is_active == True`).
- **Librarian Only (`librarian`):** Administrative endpoints restricted to staff. Non-librarians receive `403 Forbidden`.

---

## 2. System Endpoints

### `GET /api/health`
Health check endpoint reporting application readiness and database connectivity.

- **Auth Required:** None (Public)
- **Response `200 OK`:**
  ```json
  {
    "status": "healthy",
    "project_name": "AI Library Management System",
    "environment": "development",
    "database": "connected"
  }
  ```

---

## 3. Authentication Endpoints

### `POST /api/auth/login`
Authenticates user credentials and issues session cookies.

- **Auth Required:** None (Public; exempt from CSRF token check, Origin check enforced)
- **Request Body (`application/json`):**
  ```json
  {
    "email": "demo_student@library.local",
    "password": "StudentDemo123!"
  }
  ```
- **Response `200 OK`:** Sets `access_token` (`HttpOnly`) and `csrf_token` cookies.
  ```json
  {
    "id": 1,
    "email": "demo_student@library.local",
    "full_name": "Demo Student",
    "role": "student",
    "is_active": true,
    "created_at": "2026-10-26T20:06:32"
  }
  ```
- **Errors:**
  - `401 Unauthorized`: `{"detail": "Invalid email or password."}` (Uniform generic error for wrong email, bad password, or inactive account).
  - `422 Unprocessable Content`: Validation failure on input fields.

### `PATCH /api/auth/me`
Updates patron profile details (PORT-06). Only `full_name` can be updated; extra fields are rejected with 422.

- **Auth Required:** Active User (`student`, `teacher`, or `librarian`)
- **Headers:** `X-CSRF-Token: <token>`, `Origin: <origin>`
- **Request Body (`application/json`):**
  ```json
  {
    "full_name": "Alice M. Wonderland"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "id": 1,
    "email": "student@library.org",
    "full_name": "Alice M. Wonderland",
    "role": "student",
    "is_active": true,
    "created_at": "2026-10-31T00:00:00Z"
  }
  ```

### `POST /api/auth/change-password`
Securely updates the authenticated user's password with bcrypt hashing (PORT-06).

- **Auth Required:** Active User
- **Headers:** `X-CSRF-Token: <token>`, `Origin: <origin>`
- **Request Body (`application/json`):**
  ```json
  {
    "current_password": "OldPassword123!",
    "new_password": "NewStrongPassword999!"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "message": "Password updated successfully."
  }
  ```

### `POST /api/auth/logout`
Terminates the session and deletes authentication cookies.

- **Auth Required:** None (Exempt from CSRF token check, Origin check enforced)
- **Response `200 OK`:** Deletes `access_token` and `csrf_token` cookies.
  ```json
  {
    "message": "Logged out successfully."
  }
  ```

### `GET /api/auth/me`
Retrieves the profile of the currently logged-in user.

- **Auth Required:** Active User (`student` or `librarian`)
- **Response `200 OK`:**
  ```json
  {
    "id": 1,
    "email": "demo_student@library.local",
    "full_name": "Demo Student",
    "role": "student",
    "is_active": true,
    "created_at": "2026-10-26T20:06:32"
  }
  ```
- **Errors:**
  - `401 Unauthorized`: Missing, expired, or invalid session token.

---

## 4. Catalogue & Physical Copies Endpoints

### `GET /api/books`
Returns a paginated list of catalogued book titles.

- **Auth Required:** Active User (`student` or `librarian`)
- **Query Parameters:**
  - `page` *(integer, optional, default: 1)*: Page number (min: 1).
  - `page_size` *(integer, optional, default: 20)*: Items per page (min: 1, max: 100).
  - `search` / `q` *(string, optional)*: Substring filter against title, author, or ISBN. Accepts either parameter name (`q` is supported as a backward-compatible alias).
  - `category` *(string, optional)*: Exact category filter.
  - `include_archived` *(boolean, optional, default: false)*: When `true`, includes soft-archived books (librarians only; ignored for students).
- **Response `200 OK`:**
  ```json
  {
    "items": [
      {
        "id": 1,
        "title": "Designing Distributed Microservices and Event Meshes",
        "author": "Elena Rostova",
        "isbn": "9780134685991",
        "category": "Computer Science",
        "description": "Architectural principles for high-throughput distributed systems...",
        "is_archived": false,
        "total_copies": 2,
        "available_copies": 1,
        "created_at": "2026-10-26T20:06:32",
        "updated_at": "2026-10-26T20:06:32"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
  ```

### `POST /api/books`
Creates a new monograph record in the catalogue.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Request Body:**
  ```json
  {
    "title": "Quantum Cryptography and Secure Communications",
    "author": "Dr. Kenneth Moore",
    "isbn": "9780521876582",
    "category": "Cybersecurity",
    "description": "Foundations of quantum key distribution protocols and BB84."
  }
  ```
- **Response `201 Created`:** Returns `BookResponse`.
- **Errors:**
  - `400 Bad Request`: Duplicate ISBN or invalid ISBN-10/ISBN-13 checksum.
  - `403 Forbidden`: Authenticated user is not a librarian.

### `GET /api/books/{book_id}`
Retrieves full monograph metadata including its physical copy inventory.

- **Auth Required:** Active User (`student` or `librarian`)
- **Response `200 OK`:**
  ```json
  {
    "id": 1,
    "title": "Designing Distributed Microservices and Event Meshes",
    "author": "Elena Rostova",
    "isbn": "9780134685991",
    "category": "Computer Science",
    "description": "Architectural principles for high-throughput distributed systems...",
    "is_archived": false,
    "total_copies": 2,
    "available_copies": 1,
    "created_at": "2026-10-26T20:06:32",
    "updated_at": "2026-10-26T20:06:32",
    "copies": [
      {
        "id": 1,
        "book_id": 1,
        "copy_code": "CS-DIST-001",
        "operational_status": "available",
        "is_borrowed": true,
        "effective_status": "borrowed",
        "notes": "Main Stack, Level 2",
        "added_at": "2026-10-26T20:06:32"
      },
      {
        "id": 2,
        "book_id": 1,
        "copy_code": "CS-DIST-002",
        "operational_status": "available",
        "is_borrowed": false,
        "effective_status": "available",
        "notes": "Reserve Desk",
        "added_at": "2026-10-26T20:06:32"
      }
    ]
  }
  ```
- **Errors:**
  - `404 Not Found`: Book ID does not exist or is archived (for students).

### `PATCH /api/books/{book_id}`
Updates metadata fields of an existing book.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Request Body:** Partial update fields (`title`, `author`, `isbn`, `category`, `description`, `is_archived`).
- **Response `200 OK`:** Returns updated `BookResponse`.
- **Errors:**
  - `404 Not Found`: Book not found.
  - `409 Conflict`: ISBN already in use by another monograph.

### `POST /api/books/{book_id}/archive` (and `DELETE /api/books/{book_id}`)
Soft-archives a book, preserving historical loans and copy relationships.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Response `200 OK`:** Returns `BookResponse` with `is_archived: true`.

### `GET /api/books/{book_id}/copies`
Lists physical barcode copies associated with a book.

- **Auth Required:** Active User (`student` or `librarian`)
- **Response `200 OK`:** Array of `BookCopyResponse`.

### `POST /api/books/{book_id}/copies`
Registers a new physical copy with an accession barcode.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Request Body:**
  ```json
  {
    "copy_code": "CS-DIST-003",
    "operational_status": "available",
    "notes": "Study Room 2"
  }
  ```
- **Response `201 Created`:** Returns `BookCopyResponse`.
- **Errors:**
  - `400 Bad Request`: Invalid operational status (cannot be `'borrowed'`).
  - `409 Conflict`: Barcode `copy_code` already registered.

### `GET /api/copies/{copy_id}`
Retrieves details of an individual copy by its unique copy ID.

- **Auth Required:** Active User

### `PATCH /api/copies/{copy_id}`
Updates operational condition (`available`, `maintenance`, `lost`, `retired`) or notes.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Request Body:**
  ```json
  {
    "operational_status": "maintenance",
    "notes": "Binding repair in progress"
  }
  ```
- **Response `200 OK`:** Returns updated `BookCopyResponse`.

### `DELETE /api/copies/{copy_id}`
Permanently deletes a physical copy record (only permitted if the copy has no past or active loans).

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Response `200 OK`:** `{"message": "Copy deleted successfully."}`
- **Errors:**
  - `409 Conflict`: Copy has associated historical or active loans; deletion blocked by referential integrity.

---

## 5. Loan Circulation Endpoints

### `POST /api/loans` (and `POST /api/loans/issue`)
Issues a physical book copy to an eligible student.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Request Body:**
  ```json
  {
    "student_id": 1,
    "copy_id": 2
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "id": 3,
    "student_id": 1,
    "student_name": "Demo Student",
    "student_email": "demo_student@library.local",
    "copy_id": 2,
    "copy_code": "CS-DIST-002",
    "book_id": 1,
    "book_title": "Designing Distributed Microservices and Event Meshes",
    "book_author": "Elena Rostova",
    "issued_by_id": 2,
    "issued_at": "2026-10-31T00:50:00",
    "due_date": "2026-11-14",
    "returned_at": null,
    "status": "active",
    "is_overdue": false
  }
  ```
- **Circulation Policy Enforcement & Errors:**
  - `400 Bad Request`:
    - Student account is inactive.
    - Copy operational status is not `"available"` (e.g. `maintenance`, `lost`).
    - Student already has 3 active loans (concurrency limit reached).
    - Student has one or more overdue loans (borrowing privileges suspended).
  - `404 Not Found`: Student user or physical copy ID does not exist.
  - `409 Conflict`: The copy already has an active, unreturned loan (`uix_one_active_loan_per_copy`).

### `POST /api/loans/{id}/renew`
Renews an active loan by extending its due date from the current due date (CIRC-01, CIRC-05).

- **Auth Required:** Owning patron (`student`, `teacher`) or Staff `librarian`
- **Headers:** `X-CSRF-Token: <token>`, `Origin: <origin>`
- **Extension Terms:** +14 calendar days for students, +30 calendar days for faculty teachers.
- **Constraints:** Maximum 1 renewal per loan; rejected if loan is already overdue or patron has other overdue loans.
- **Response `200 OK`:** Returns updated `LoanResponse` with incremented `renewal_count`.

### `POST /api/loans/{loan_id}/return`
Records the return of an active borrowed item.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Response `200 OK`:** Returns `LoanResponse` with populated `returned_at` timestamp and `status: "returned"`.
- **Errors:**
  - `404 Not Found`: Loan ID not found.
  - `409 Conflict`: Loan was already returned (`returned_at IS NOT NULL`).

### `GET /api/loans/me` (Aliases: `/api/loans/my`, `/api/loans/my-loans`)
Lists borrowing history and active loans for the authenticated student.

- **Auth Required:** Active User (`student` or `librarian`)
- **Tenant Isolation:** Strictly filters to `student_id == current_user.id`.
- **Query Parameters:**
  - `page` *(default: 1)*
  - `page_size` *(default: 20)*
  - `status` *(optional)*: Filter by `"active"`, `"returned"`, or `"overdue"`.
- **Response `200 OK`:** `LoanPaginationResponse`.

### `GET /api/loans`
Librarian overview of circulation across all students.

- **Auth Required:** Librarian Only (`librarian`)
- **Query Parameters:**
  - `page` *(default: 1)*
  - `page_size` *(default: 20)*
  - `student_id` *(optional)*: Filter by student ID.
  - `copy_id` *(optional)*: Filter by copy ID.
  - `book_id` *(optional)*: Filter by book ID.
  - `status` *(optional)*: `"active"`, `"returned"`, or `"overdue"`.
- **Response `200 OK`:** `LoanPaginationResponse`.

### `GET /api/loans/{loan_id}`
Retrieves a specific loan record.

- **Auth Required:** Active User (Students can only access their own loans; librarians can access any loan).
- **Errors:**
  - `403 Forbidden`: Student attempting to inspect another student's loan record.
  - `404 Not Found`: Loan ID not found.

---

## 6. Semantic & Hybrid Search & Recommendation Endpoints

### `GET /api/search/hybrid`
Performs dual-channel retrieval combining parameterized lexical SQL scoring with dense vector cosine similarity, ranked via Reciprocal Rank Fusion (RRF, $k=60.0$).

- **Auth Required:** Active User (`student` or `librarian`)
- **Query Parameters:**
  - `q` *(string, required)*: Search query string across title, author, description, and normalized ISBN identifiers (1 to 500 characters).
  - `category` *(string, optional)*: Case-insensitive category filter.
  - `page` *(integer, optional, default: 1)*: Page number within the candidate pool (min: 1).
  - `page_size` *(integer, optional, default: 10)*: Results per page (min: 1, max: 50).
  - `min_score` *(float, optional, default: -1.0, range: -1.0 to 1.0)*: Minimum cosine similarity threshold for the semantic vector channel.
- **Candidate Pool Bounding & Pagination Rules:**
  - **Candidate Retrieval Limit:** The service retrieves up to 100 lexical candidates and up to 100 semantic candidates.
  - **Bounded Fusion Union:** The fused candidate pool contains at most 200 items ($|\text{Lexical}_{100} \cup \text{Semantic}_{100}| \le 200$).
  - **Pagination Scope:** `page` and `page_size` operate strictly across the bounded fused candidate pool. Monograph records falling outside the top 100 of both channels are omitted from the candidate pool and cannot be reached by advancing page numbers.
- **Count Semantics:**
  - `total_lexical_matches`: Exhaustive database count of all non-archived books matching the lexical SQL conditions.
  - `total_semantic_matches`: Count of all non-archived books meeting the semantic cosine similarity threshold.
  - `total_fused_candidates`: Count of unique items in the fused candidate pool ($\le 200$).
  - `total`: **Mirrors `total_fused_candidates`**. Indicates the size of the fused candidate pool available for pagination, **not** an unconstrained catalogue count.
  - `total_pages`: Total pages available within the fused candidate pool ($\lceil \text{total} / \text{page\_size} \rceil$).
- **Response `200 OK`:**
  ```json
  {
    "items": [
      {
        "id": 1,
        "title": "Essential Cloud Computing Systems: Case Studies",
        "author": "Heather Cook",
        "isbn": "978-0-530-00001-5",
        "category": "Computer Science",
        "description": "Architectural principles for high-throughput distributed systems...",
        "total_copies": 5,
        "available_copies": 4,
        "rrf_score": 0.032787,
        "lexical_rank": 1,
        "semantic_rank": 1,
        "similarity_score": 0.8412,
        "match_channels": ["lexical", "semantic"]
      }
    ],
    "total": 35,
    "page": 1,
    "page_size": 10,
    "total_pages": 4,
    "total_lexical_matches": 35,
    "total_semantic_matches": 48,
    "total_fused_candidates": 35,
    "query": "Essential Cloud Computing Systems",
    "applied_category": null,
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "fusion_method": "Reciprocal Rank Fusion (k=60)"
  }
  ```

### `GET /api/search/semantic`
Performs neural vector semantic search against book titles, authors, categories, and descriptions.

- **Auth Required:** Active User (`student` or `librarian`)
- **Query Parameters:**
  - `q` *(string, required)*: Natural language search query.
  - `page` *(default: 1)*: Page number.
  - `page_size` *(default: 10, max: 50)*: Results per page.
  - `min_score` *(float, default: -1.0, range: -1.0 to 1.0)*: Minimum cosine similarity threshold.
- **Response `200 OK`:**
  ```json
  {
    "items": [
      {
        "id": 1,
        "title": "Designing Distributed Microservices and Event Meshes",
        "author": "Elena Rostova",
        "isbn": "9780134685991",
        "category": "Computer Science",
        "description": "Architectural principles for high-throughput distributed systems...",
        "total_copies": 2,
        "available_copies": 1,
        "similarity_score": 0.7421
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10,
    "total_pages": 1,
    "query": "distributed streaming event pipelines",
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "disclaimer": "Similarity scores represent vector cosine similarity (-1.0 to 1.0)..."
  }
  ```

### `GET /api/books/{book_id}/recommendations`
Generates content-based book recommendations based on vector cosine similarity with the target book.

- **Auth Required:** Active User (`student` or `librarian`)
- **Query Parameters:**
  - `limit` *(integer, default: 5, min: 1, max: 20)*: Number of similar monographs to return.
- **Response `200 OK`:**
  ```json
  {
    "source_book_id": 1,
    "source_book_title": "Designing Distributed Microservices and Event Meshes",
    "recommendations": [
      {
        "id": 2,
        "title": "Database Internals: Storage Engines and Query Optimization",
        "author": "Arthur Pendelton",
        "isbn": "9781491950357",
        "category": "Computer Science",
        "description": "Comprehensive dive into B-Trees, LSM trees, write-ahead logging...",
        "similarity_score": 0.5891
      }
    ],
    "total": 1,
    "method": "content-based-cosine-similarity",
    "disclaimer": "Recommendations are content-based comparisons derived from text embeddings..."
  }
  ```

### `GET /api/embeddings/status`
Returns metrics on vector coverage and embedding model availability.

- **Auth Required:** Librarian Only (`librarian`)
- **Response `200 OK`:**
  ```json
  {
    "total_books": 15,
    "with_embedding": 15,
    "missing_embedding": 0,
    "stale_embedding": 0,
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "model_available": true,
    "is_processing": false
  }
  ```

### `POST /api/embeddings/refresh`
Generates missing embeddings and updates stale vectors when book metadata has changed.

- **Auth Required:** Librarian Only (`librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Query Parameters:**
  - `force_refresh` *(boolean, default: false)*: When `true`, re-encodes all monographs regardless of staleness.
- **Response `200 OK`:**
  ```json
  {
    "status": "success",
    "total_candidates": 15,
    "processed": 0,
    "failed": 0,
    "stale": 0,
    "missing": 0,
    "message": "Embeddings are up to date.",
    "errors": []
  }
  ```

---

## 7. AI Library Copilot Endpoint

### `POST /api/copilot/chat`
Conversational library assistant answering inquiries about books, personal due dates, and library policies.

- **Auth Required:** Active User (`student` or `librarian`)
- **Headers:** `X-CSRF-Token: <token>`
- **Request Body:**
  ```json
  {
    "message": "What books do I currently have checked out?",
    "conversation_history": [
      {
        "role": "user",
        "content": "Hello"
      },
      {
        "role": "assistant",
        "content": "Hello Demo Student! Welcome to the AI Library. How can I assist you today?"
      }
    ]
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "reply": "You currently have 1 active loan:\n• Designing Distributed Microservices and Event Meshes (Barcode: CS-DIST-001) — Due on 2026-11-12",
    "provider": "fallback",
    "is_fallback": true,
    "sources": [
      {
        "type": "loan",
        "id": 1,
        "title": "Designing Distributed Microservices and Event Meshes",
        "snippet": "Barcode CS-DIST-001, Due: 2026-11-12, Status: active",
        "author": "Elena Rostova",
        "category": "Computer Science",
        "available_copies": 1,
        "total_copies": 2
      }
    ],
    "suggested_followups": [
      "How do I return a book?",
      "Can I renew my borrowed books?",
      "What is the standard borrowing duration?"
    ]
  }
  ```
- **Input Constraints & Defenses:**
  - Maximum query length: 500 characters.
  - Strips non-printable ASCII control characters.
  - Strips LLM chat delimiters (`<|im_start|>`, `<|im_end|>`).
  - Sliding-window rate limit: 25 requests per minute per user.
- **Errors:**
  - `400 Bad Request`: Query exceeds 500 characters or contains malicious syntax.
  - `429 Too Many Requests`: Rate limit exceeded.



---

## 8. Notifications Endpoints (CIRC-04)

### `GET /api/notifications`
Returns paginated in-app alerts and overdue warnings for the authenticated user.

- **Auth Required:** Active User (`student`, `teacher`, `librarian`)
- **Query Parameters:**
  - `page`: Page number (default: `1`)
  - `page_size`: Results per page (default: `20`, max: `100`)
  - `unread_only`: Filter for unread notifications only (default: `false`)

### `GET /api/notifications/unread-count`
Returns the count of unread notifications for badge indicators in UI navigation.

- **Auth Required:** Active User
- **Response `200 OK`:**
  ```json
  {
    "unread_count": 2
  }
  ```

### `PATCH /api/notifications/{id}/read`
Marks a specific notification as read. The notification must belong to the caller.

- **Auth Required:** Owning patron or staff librarian

### `POST /api/notifications/mark-all-read`
Bulk marks all unread notifications for the caller as read.

- **Auth Required:** Active User

### `POST /api/notifications/sweep`
Manually triggers an automated overdue loan sweep across active circulation records.

- **Auth Required:** Librarian Only (`require_librarian`)
- **Query Parameters:** `as_of_date` (optional baseline evaluation date in `YYYY-MM-DD` format)
- **Response `200 OK`:**
  ```json
  {
    "new_notifications": 3
  }
  ```
