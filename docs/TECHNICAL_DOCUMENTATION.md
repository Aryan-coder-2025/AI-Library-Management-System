# Athenaeum: Comprehensive Technical Documentation & Architecture Report

---

# Chapter 1 — Introduction and Project Vision

## 1.1 Executive Summary
**Athenaeum** is an enterprise-grade, artificial intelligence-augmented Smart Library Management System engineered specifically for modern academic institutions, universities, and research centers. The system synthesizes traditional physical library operations—such as physical copy barcode tracking, patron circulation lifecycles, and reservation quotas—with modern spatial wayfinding, dense semantic discovery, external scholarly research retrieval, and an agentic multi-pillar artificial intelligence engine.

Academic libraries operate under constraints distinct from commercial retail or general inventory systems:
1. Resources are physical, finite, and circulating, requiring strict concurrency control, reservation queues, and anti-collision safeguards.
2. Space itself is an academic asset; modern libraries manage hundreds of individual study carrels, group collaboration rooms, silent study zones, and multi-level floor plans.
3. Information discovery must transcend literal keyword matching. Students and faculty require conceptual exploration across academic disciplines, dense semantic search, verifiable retrieval-augmented generation (RAG) with structured citations, and seamless connectivity to global open-access research repositories.

Athenaeum provides a unified, cohesive platform that fulfills these academic and operational needs while maintaining uncompromising data integrity, transparent offline deterministic fallbacks, and strict role-based access control.

## 1.2 The Problem Space
Conventional Integrated Library Systems (ILS) and Online Public Access Catalogs (OPAC) suffer from deep architectural limitations:
- **Keyword Brittleness**: Traditional lexical matching (such as BM25 or raw SQL `LIKE` queries) fails when patrons do not know the exact cataloging terminology, author spelling, or precise monograph title. A student searching for *"reinforcement learning in autonomous vehicles"* may miss seminal texts indexed under *"Optimal Control"* or *"Markov Decision Processes"*.
- **Physical-Digital Disconnect**: Catalog records indicate that a physical volume is *"Available on Shelf 3B"*, but provide zero spatial wayfinding, visual floor guidance, or real-time occupancy context. Patrons wander physical stacks without directional guidance.
- **Hallucinatory AI Chatbots**: Generic large language model wrappers deployed on library websites frequently hallucinate non-existent books, invent false shelf locations, leak patron loan histories across sessions, and provide unverified academic claims without provenance.
- **Fragmented Workflows**: Institutional research discovery is typically fragmented across commercial proprietary silos (IEEE, ScienceDirect), pre-print servers (arXiv), open metadata aggregators (OpenAlex, Crossref), and local physical inventory, forcing students to navigate multiple disjointed interfaces.

## 1.3 Project Objectives
Athenaeum was designed and implemented to resolve these architectural shortcomings through the following core objectives:
1. **Unified Operational Excellence**: Complete digital automation of all circulation desks, barcode tracking, loan renewals, waitlists, holds, lost/damaged item processing, and course reserves.
2. **Dense Semantic & Hybrid Discovery**: Multi-modal search blending BM25-style lexical ranking with 384-dimensional dense vector embeddings via Reciprocal Rank Fusion (RRF).
3. **Interactive Spatial Mapping & Wayfinding**: Multi-floor SVG layout visualization, live desk and room occupancy tracking, and Dijkstra shortest-path turn-by-turn physical navigation.
4. **Verifiable Agentic AI**: A tool-calling Librarian Copilot with bounded conversational history, anti-prompt-injection safeguards, coreference resolution, and structured, verifiable citations linked directly to catalog records and institutional policies.
5. **Scholarly Aggregation**: Real-time parallel integration with external academic repositories (OpenAlex, arXiv, Crossref) with automated DOI deduplication and rate-limit handling.
6. **Executive Intelligence & Forecasting**: Holt-Winters time-series circulation demand forecasting, collection turnover analytics, zero-borrow monograph detection, and automated acquisition recommendation scoring.

## 1.4 Intended User Personas
Athenaeum defines five explicit user roles, each with custom permission boundaries and dedicated interface workflows:
1. **Public Guest (OPAC)**: Unauthenticated visitor capable of browsing the catalog, checking high-level title availability, and searching academic research. Physical copy barcodes, internal patron details, and loan histories are strictly masked.
2. **Student Patron**: Authenticated undergraduate or postgraduate student. Entitled to borrow up to 5 monographs simultaneously for 14-day loan terms, reserve study seats (up to 4 hours) and rooms (up to 3 hours), place holds on exhausted titles, generate cryptographic QR collection tokens, and interact with the AI Copilot.
3. **Teacher / Faculty**: Academic instructors with elevated borrowing privileges (up to 10 monographs for 30-day loan terms, advance room bookings up to 14 days). Capable of managing academic courses, creating required course reading lists, uploading course syllabi, and placing physical copies on restricted Course Reserve status.
4. **Librarian Staff**: Operational library staff managing circulation desks, checking physical copies in and out, overriding overdue fines or loan limits, reviewing lost/damaged inventory, publishing interactive floor plans, and fulfilling hold queues.
5. **Administrator**: System overseer responsible for system configuration, AI model comparison auditing, database seeding, telemetry monitoring, and role provisioning.

## 1.5 System Boundaries & Operational Constraints
To ensure absolute reliability, the implementation adheres to strict operational boundaries:
- **No Simulated AI Claims**: When remote AI providers (e.g., Google Gemini or OpenAI) are active, responses are explicitly marked as live API results. When unconfigured or offline, the system seamlessly transitions to a deterministic factual synthesis engine grounded in live database queries, clearly labeled as a local fallback.
- **Storage-Level Foreign Key Integrity**: Relational constraints are enforced at the storage level via SQLite `PRAGMA foreign_keys = ON`.
- **Database Immutability Safeguards**: Canonical baseline databases are protected by runtime hash checks, preventing accidental test corruption or unapproved schema migrations against production data.

---

# Chapter 2 — System Overview

## 2.1 Major Subsystems
Athenaeum is partitioned into eight loosely coupled, highly cohesive subsystems:

```mermaid
graph TD
    subgraph Subsystems ["Athenaeum Core Subsystems"]
        SUB_AUTH["1. Authentication & Identity Management"]
        SUB_CAT["2. Catalogue & Hybrid Discovery Engine"]
        SUB_CIRC["3. Circulation, Holds & QR Operations"]
        SUB_SPACE["4. Study Spaces & Dijkstra Wayfinding"]
        SUB_AI["5. Multi-Pillar AI & Grounded Copilot"]
        SUB_ACAD["6. External Academic Research Aggregator"]
        SUB_COURSE["7. Course Management & Academic Reserves"]
        SUB_INTEL["8. Librarian Intelligence & Forecasting"]
    end
```

1. **Authentication & Identity Management**: Manages student registration, dual-identifier login (email or username), bcrypt password hashing, session tokens, and cryptographic password recovery over SMTP.
2. **Catalogue & Hybrid Discovery Engine**: Indexes physical monographs, assigns ISBNs, extracts metadata, computes dense sentence embeddings, and executes Reciprocal Rank Fusion across lexical and vector channels.
3. **Circulation, Holds & QR Operations**: Orchestrates the complete loan lifecycle (checkout, renewal, return, overdue penalties), FIFO hold queue allocation with pickup timers, and secure QR-code physical collection verification.
4. **Study Spaces & Spatial Wayfinding**: Manages floor plans, study zones, study desks, and group rooms; calculates real-time occupancy and computes shortest-path turn-by-turn navigation via Dijkstra's graph traversal.
5. **Multi-Pillar AI & Grounded Copilot**: Multi-turn conversational agent with coreference resolution and tool dispatching, multi-model evaluation studio, and hierarchical knowledge graph visualization (`Subject` $\rightarrow$ `Topic` $\rightarrow$ `Concept`).
6. **External Academic Research Aggregator**: Parallel asynchronous client querying OpenAlex, arXiv, and Crossref with automatic result deduplication and structured citation formatting.
7. **Course Management & Academic Reserves**: Enables instructors to manage courses, syllabus attachments, and reading lists, while enforcing strict 2-hour or overnight course reserve circulation policies.
8. **Librarian Intelligence & Forecasting**: Aggregates longitudinal circulation metrics to calculate turnover velocity, identify stale monograph inventory, and forecast upcoming circulation demand using exponential smoothing.

## 2.2 System Architecture Diagram

```mermaid
flowchart TB
    ClientBrowser["Client Browser (React 19 + TypeScript + Vite)"]
    
    subgraph Gateway ["Edge & Security Middleware"]
        CORS["CORS Middleware"]
        AuthGuard["JWT Auth / Cookie Guard"]
        RateLimiter["In-Memory Rate Limiter"]
    end

    subgraph Application ["FastAPI Asynchronous Application Layer"]
        RouterLayer["Modular Domain Routers (15 Routers)"]
        ServiceLayer["Domain Services (16 Service Engines)"]
    end

    subgraph Persistence ["Persistence & Analytics Store"]
        RelationalDB[("Relational Database (SQLite / PostgreSQL)\n31 Tables, Foreign Keys, Indexes")]
        VectorStore["Serialized 384-dim BLOB Vector Store"]
    end

    subgraph ExternalServices ["External Service Integrations"]
        GoogleGemini["Google Gemini API (3.1-flash-lite)"]
        OpenAI["OpenAI API (GPT-4o)"]
        OllamaLocal["Local Ollama Daemon (Port 11434)"]
        ScholarlyAPIs["OpenAlex, arXiv, Crossref APIs"]
        MailRelay["University SMTP Mail Relay (Port 587)"]
    end

    ClientBrowser <--> Gateway
    Gateway <--> Application
    Application <--> Persistence
    ServiceLayer <--> ExternalServices
```

---

# Chapter 3 — Technology Stack

## 3.1 Technology Inventory & Architectural Rationale

| Domain | Technology | Verified Version | Primary Codebase Location | Architectural Responsibility |
|---|---|---|---|---|
| **Backend Framework** | FastAPI | `0.110+` (installed: `0.162.0`) | `backend/app/main.py`, `routers/` | Asynchronous REST routing, OpenAPI schema generation, dependency injection. |
| **ASGI Server** | Uvicorn (standard) | `0.28+` (installed: `0.54.0`) | Backend process runtime | High-concurrency event-loop worker server. |
| **ORM & Database Toolkit** | SQLAlchemy | `2.0+` (installed: `2.1.6`) | `backend/app/models.py`, `database.py` | Relational object modeling, declarative schema mapping, connection pooling. |
| **Data Validation** | Pydantic & Pydantic-Settings | `2.6+` (installed: `2.14.1` / `2.16.1`) | `backend/app/schemas.py`, `config.py` | Request/response serialization, typing enforcement, `.env` parsing. |
| **Database Migrations** | Alembic | `1.13+` (installed: `1.20.1`) | `backend/alembic/` | Declarative, version-controlled schema evolution and downgrade migrations. |
| **Authentication & Crypto** | Passlib (Bcrypt) & Python-Jose | `passlib 1.7.4`, `python-jose 3.5.0` | `backend/app/auth.py` | Password hashing (12-round bcrypt), cryptographic JWT issuance and signing. |
| **HTTP Client** | HTTPX | `0.27+` (installed: `0.28.1`) | `backend/app/services/research/`, `copilot.py` | Asynchronous HTTP queries to external LLM and academic research APIs. |
| **Dense Vector Embeddings** | SentenceTransformers | `2.3+` (installed: `6.2.0`) | `backend/app/services/embedding.py` | Local dense vector inference (`all-MiniLM-L6-v2`, 384 dimensions). |
| **Numerical Computation** | NumPy | `1.26+` (installed: `2.4.6`) | `backend/app/services/semantic.py`, `embedding.py` | Vector cosine similarity calculation, vector serialization to byte BLOBs. |
| **Testing Framework** | Pytest & Pytest-Asyncio | `pytest 8.1+` (installed: `8.4.2`) | `backend/tests/` | Unit, integration, security, and migration test automation. |
| **Frontend Framework** | React | `19.3.1` | `frontend/src/` | Component hierarchy, stateful UI hooks, virtual DOM rendering. |
| **Type System** | TypeScript | `~6.0.3` (installed: `5.8+` engine) | `frontend/src/types/`, entire frontend | Full client-side static type safety. |
| **Build Tooling & Dev Server** | Vite | `5.4.11` | `frontend/vite.config.ts` | ESM hot-module reloading, Rollup bundling, CSS asset pipeline. |
| **QR Code Generation** | QRCode (npm) | `1.5.4` | `frontend/src/components/QRCodeModal.tsx` | Client-side Canvas/SVG QR rendering for physical collection tokens. |
| **Styling & Design System** | Tailwind CSS / Vanilla CSS | Embedded modern CSS variables | `frontend/src/index.css` | Glassmorphic dark/light design system, fluid typography, responsive layout. |

---

# Chapter 4 — Frontend Architecture

## 4.1 Application Directory Structure
The frontend application is structured into domain-specific components, custom hooks, and shared services:

```
frontend/src/
├── App.tsx                     # Core application layout, role state, modal routing
├── main.tsx                    # React DOM root entry point
├── index.css                   # Glassmorphism design tokens, CSS variables, utility classes
├── types/
│   └── library.ts              # TypeScript interfaces for all backend models & schemas
├── services/
│   └── theme.ts                # Theme preference manager (Dark, Light, System)
└── components/
    ├── Navbar.tsx              # Top navigation bar, role selector, user pill, notifications
    ├── CommandPalette.tsx      # Global Cmd+K / Ctrl+K keyboard shortcut palette
    ├── AICopilotDrawer.tsx     # Slide-over AI Copilot chat drawer with RAG citations
    ├── SignIn.tsx              # Dual-identifier login interface (email/username)
    ├── Register.tsx            # Student self-registration form
    ├── ForgotPassword.tsx      # Password reset request view
    ├── ResetPassword.tsx       # Password reset token confirmation view
    ├── PatronProfileModal.tsx  # User profile editor and password change modal
    ├── BookDetailModal.tsx     # Monograph details, copy status, hold placement, recommendations
    ├── CopyStatusModal.tsx     # Librarian lost/damaged inventory transition modal
    ├── QRCollectionModal.tsx   # Cryptographic QR token generator & scanner modal
    ├── StudentCatalogue.tsx    # Student book catalog with lexical, semantic, hybrid search
    ├── StudentLoans.tsx        # Active loans, hold queue status, loan history, QR triggers
    ├── StudentSpaces.tsx       # Study seat and room reservation dashboard
    ├── TeacherPortal.tsx       # Faculty reading list manager, course creation, syllabus upload
    ├── LibrarianCirculation.tsx# Desk checkout/return, hold fulfillment, patron lookups
    ├── LibrarianCatalogue.tsx  # Physical book management, barcode assignment, copy auditing
    ├── intelligence/
    │   └── LibrarianIntelligenceCenter.tsx # Demand forecasting, turnover KPIs, acquisition orders
    ├── knowledge/
    │   ├── KnowledgeExplorer.tsx          # Hierarchical Concept Graph browser
    │   └── ModelComparisonStudio.tsx      # Side-by-side LLM auditing studio
    ├── research/
    │   └── AcademicResearchDiscovery.tsx  # OpenAlex, arXiv, Crossref search portal
    └── spatial/
        ├── FloorPlanCanvas.tsx            # Interactive SVG floor plan renderer
        ├── StudentFloorPlan.tsx           # Desk selection and turn-by-turn wayfinding
        └── LibrarianFloorPlanManager.tsx  # Floor plan editor and element mapper
```

## 4.2 State Management & Session Lifecycle
Athenaeum avoids third-party global state libraries in favor of React's built-in composition model:
- **Authentication State**: Lifted to `App.tsx`. Upon initial mount, the application invokes `GET /api/v1/auth/me`. The response initializes the active user profile, assigned role (`guest`, `student`, `teacher`, `librarian`, `admin`), active loan count, and pending notifications.
- **Optimistic UI Updates**: Workflows such as renewing loans, reserving study seats, or toggling book holds perform optimistic local state mutations, rolling back immediately if the asynchronous API call returns an HTTP error code.
- **Session Expiration Guard**: An HTTP interceptor catches `401 Unauthorized` responses and smoothly transitions the user interface to the login state without disruptive page refreshes.

---

# Chapter 5 — Backend Architecture

## 5.1 Request Lifecycle & Middleware Pipeline
Every HTTP request entering the FastAPI backend traverses an explicit, defense-in-depth pipeline:

```mermaid
sequenceDiagram
    autonumber
    participant Client as Client Browser
    participant CORS as CORSMiddleware
    participant Rate as RateLimiter
    participant Auth as AuthDependency
    participant Route as Router Handler
    participant Svc as Domain Service
    participant DB as SQLite / PostgreSQL

    Client->>CORS: HTTP Request (Headers + Cookies)
    CORS->>CORS: Validate Origin against ALLOWED_ORIGINS
    CORS->>Rate: Forward Request
    Rate->>Rate: Check User IP / ID Rate Limits (25 req/min)
    Rate->>Auth: Forward to Route Dependencies
    Auth->>Auth: Extract 'access_token' Cookie, Verify JWT
    Auth->>DB: Fetch Active User & Verify Role Permissions
    DB-->>Auth: User Entity Verified
    Auth->>Route: Inject (db: Session, current_user: User)
    Route->>Svc: Execute Business Logic with atomic_write
    Svc->>DB: SQL Queries & Mutation Expressions
    DB-->>Svc: Transaction Committed
    Svc-->>Route: Return Pydantic Schema Model
    Route-->>Client: 200 OK (JSON Payload)
```

## 5.2 Dependency Injection & Database Sessions
FastAPI's dependency injection system guarantees clean resource isolation:
- `get_db()`: Yields an isolated SQLAlchemy `Session` bound to the active thread/task. Sessions are automatically closed in `finally` blocks upon request completion.
- `atomic_write(db)`: A context manager wrapping write transactions in explicit `BEGIN...COMMIT` blocks. If any exception occurs during processing, an automatic `db.rollback()` is executed, preventing partial writes and dangling transactions.
- `get_current_user()` and `require_role(role)`: Modular dependencies that validate credentials, decode JWT signatures, and assert that the authenticated patron possesses the necessary authorization level.

---

# Chapter 6 — Database Design & Invariant Hardening

## 6.1 Relational Entity Specifications
The Athenaeum database schema contains 31 relational tables linked by strict foreign keys, check constraints, and performance indexes. The table below details the most critical production tables:

| Table Name | Entity Class | Primary Key | Foreign Keys | Key Columns & Constraints | Purpose |
|---|---|---|---|---|---|
| `users` | `User` | `id` (INTEGER) | None | `email` (UNIQUE), `username` (UNIQUE), `hashed_password`, `role` (CHECK: student, teacher, librarian, admin) | Patron and staff identity directory. |
| `books` | `Book` | `id` (INTEGER) | None | `isbn` (UNIQUE, VARCHAR 20), `title`, `author`, `category`, `embedding` (BLOB), `is_archived` | Monograph title metadata and dense vector storage. |
| `book_copies` | `BookCopy` | `id` (INTEGER) | `book_id` $\rightarrow$ `books.id` | `barcode` (UNIQUE), `condition` (good, fair, poor, damaged, lost), `status` (available, on_loan, reserved, course_reserve) | Physical inventory tracking and circulation status. |
| `loans` | `Loan` | `id` (INTEGER) | `user_id`, `book_copy_id` | `borrowed_at`, `due_date`, `returned_at`, `renewal_count`, `status` (active, returned, overdue) | Active and historical borrowing circulation records. |
| `book_holds` | `BookHold` | `id` (INTEGER) | `user_id`, `book_id`, `allocated_copy_id` | `placed_at`, `ready_at`, `expires_at`, `queue_position`, `status` (pending, ready_for_pickup, fulfilled, cancelled, expired) | Waitlist management for exhausted monograph titles. |
| `book_collection_tokens` | `BookCollectionToken` | `id` (INTEGER) | `user_id`, `book_id`, `book_copy_id` | `token` (UNIQUE, 32-byte hash), `expires_at`, `consumed_at` | Cryptographic QR tokens for touchless checkout verification. |
| `courses` | `Course` | `id` (INTEGER) | `instructor_id` $\rightarrow$ `users.id` | `course_code` (UNIQUE), `course_name`, `academic_term`, `syllabus_filename` | Academic courses instructing reading lists. |
| `course_reading_list_items` | `CourseReadingListItem` | `id` (INTEGER) | `course_id`, `book_id` | `is_required` (BOOLEAN), `notes` | Required and recommended monographs for a course. |
| `course_reserves` | `CourseReserve` | `id` (INTEGER) | `course_id`, `book_id` | `max_loan_hours` (default 2), `active_until`, `status` | Restricted short-loan reserve status enforcement. |
| `library_floors` | `LibraryFloor` | `id` (INTEGER) | None | `floor_number`, `name`, `is_active` | Physical building levels for spatial floor plans. |
| `study_zones` | `StudyZone` | `id` (INTEGER) | `floor_id` $\rightarrow$ `library_floors.id` | `zone_code` (UNIQUE), `noise_policy` (silent, quiet, collaborative) | Acoustic and functional zones within library floors. |
| `study_seats` | `StudySeat` | `id` (INTEGER) | `zone_id` $\rightarrow$ `study_zones.id` | `seat_code` (UNIQUE), `has_power`, `is_accessible` | Individual study carrels and desks. |
| `study_rooms` | `StudyRoom` | `id` (INTEGER) | `zone_id` $\rightarrow$ `study_zones.id` | `room_code` (UNIQUE), `capacity`, `has_projector` | Group collaboration and meeting rooms. |
| `reservations` | `Reservation` | `id` (INTEGER) | `user_id`, `seat_id`, `room_id` | `start_time`, `end_time`, `checked_in_at`, `status` (active, completed, cancelled, no_show) | Time-bounded bookings for seats and study rooms. |
| `spatial_resource_mappings` | `SpatialResourceMapping` | `id` (INTEGER) | `floor_id` | `resource_type` (seat, room, zone), `resource_id`, `x`, `y`, `label` | Georeferenced Cartesian coordinates for SVG floor maps. |
| `wayfinding_nodes` | `WayfindingNode` | `id` (INTEGER) | `floor_id` | `x`, `y`, `node_type` (entrance, corridor, stairwell, elevator, destination) | Topological graph vertices for Dijkstra shortest-path navigation. |
| `wayfinding_edges` | `WayfindingEdge` | `id` (INTEGER) | `from_node_id`, `to_node_id` | `distance`, `bidirectional` | Topological graph edges connecting wayfinding waypoints. |
| `password_reset_tokens` | `PasswordResetToken` | `id` (INTEGER) | `user_id` $\rightarrow$ `users.id` | `token_hash` (UNIQUE, SHA-256), `expires_at`, `used` (BOOLEAN) | Single-use cryptographic password reset tokens over SMTP. |

## 6.2 Transactional Invariants & Concurrency Hardening
In high-concurrency environments such as university study space reservations, Athenaeum enforces mathematical transactional invariants:

### 6.2.1 Strict Booking-Time Invariant
- **Mathematical Invariant:** `start_time >= now_utc`
- **Zero Past Tolerance:** Any reservation request with a start time strictly earlier than monotonic `now_utc` ($start\_time < now\_utc$, even by 1 microsecond) is rejected with `HTTP 400 Bad Request`.
- **Clock Injection:** `validate_reservation_times` supports clock injection (`now_utc: Optional[datetime]`), enabling deterministic time-travel regression testing.
- **Timezone Normalization:** Client datetimes are parsed and normalized to naive UTC before persistence, then projected into the institutional timezone (`Asia/Kolkata`, operating hours `08:00` to `22:00`).

### 6.2.2 SQLite `BEGIN IMMEDIATE` Serialization
To eliminate Time-Of-Check-To-Time-Of-Use (TOCTOU) race conditions in SQLite:
1. `get_write_db()` issues `BEGIN IMMEDIATE` upon transaction acquisition (`{"sqlite_immediate": True}`).
2. An immediate `RESERVED` lock blocks concurrent write transactions while permitting concurrent read transactions under Write-Ahead Logging (WAL) mode.
3. Lock contention waiting exceeds the 5,000ms `busy_timeout` gracefully maps to `HTTP 503 Service Unavailable` with a standard `Retry-After: 1` header, avoiding opaque database driver crashes.

---

# Chapter 7 — Authentication and Authorization

## 7.1 Registration & Identity Model
Athenaeum enforces strict patron identity verification:
- **Public Student Registration**: Students register via `/api/v1/auth/register`, providing a valid institutional email, unique username, and full name. The backend automatically assigns the `student` role and initializes their borrowing limits.
- **Dual-Identifier Authentication**: Patrons log in via `/api/v1/auth/login` by providing their password alongside either their verified institutional email address or their unique username. The authentication service normalizes the identifier and executes an indexed database lookup.

## 7.2 Cryptographic Password Policy & Bcrypt Hashing
- **Complexity Requirements**: All user passwords must be at least 12 characters in length. This baseline is validated both client-side and server-side via Pydantic validators (`len(v) >= 12`).
- **Bcrypt Hashing**: Passwords are never stored in plaintext. They are salted and hashed using Passlib's `bcrypt` algorithm with a work factor of 12 rounds.

## 7.3 Session Tokens & Transport Security
- **Stateless JWT**: Sessions are governed by JSON Web Tokens signed with HMAC-SHA256 (`HS256`). Tokens encode the user's `sub` (user ID), username, role, and an `exp` expiration timestamp (default: 8 hours / 480 minutes).
- **HttpOnly Cookies**: JWTs are transmitted in `HttpOnly`, `SameSite=Lax` cookies named `access_token`. This prevents cross-site scripting (XSS) attacks from exfiltrating authentication tokens.
- **Campus Workstation Isolation (`is_public_device`)**: When logging in on shared library terminals or campus computer labs, patrons can designate the session as a public device. The backend omits `Max-Age` and `Expires` directives, creating a non-persistent session cookie that is purged immediately upon closing the browser tab or window.
- **Client-Side Inactivity Monitor**: An active listener (`InactivityMonitor.tsx`) tracks patron engagement across mouse movements, keypresses, and touch events. Following 25 minutes of inactivity, a security dialog is displayed warning of impending session termination; at 30 minutes, an automated zero-trust logout is executed, revoking credentials and clearing portal context.
- **CSRF & CORS Controls**: The API whitelist in `ALLOWED_ORIGINS` rejects incoming requests originating from unauthorized domains. Double-submit `csrf_token` headers are enforced on all mutative state operations.

---

# Chapter 8 — Catalogue and Hybrid Discovery Engine

## 8.1 Multi-Modal Catalog Representation
Monographs are indexed with comprehensive bibliographic metadata:
- Title, Author, ISBN-10 / ISBN-13, Subject Category, Publication Year, Description.
- Associated hierarchical concepts (`Computer Science` $\rightarrow$ `Artificial Intelligence` $\rightarrow$ `Deep Learning`).
- Pre-calculated 384-dimensional dense semantic vector embeddings.
- Physical copy barcode inventory, tracking copy conditions (`good`, `fair`, `poor`, `damaged`, `lost`) and circulation availability.

## 8.2 ISBN Normalization Pipeline
The ISBN normalization service (`backend/app/services/isbn.py`) validates and normalizes all incoming monograph identifiers:
1. Strips all formatting hyphens, spaces, and punctuation.
2. If input length is 10 characters:
   - Validates Modulo 11 checksum where final check digit `'X'` represents value 10:
     $$\sum_{i=1}^{10} (11 - i) \times d_i \equiv 0 \pmod{11}$$
   - Converts valid ISBN-10 to canonical ISBN-13 by prepending `978` and recalculating the Modulo 10 check digit.
3. If input length is 13 characters:
   - Validates alternating Modulo 10 checksum:
     $$\sum_{i=1}^{13} (1 \text{ if } i \text{ odd else } 3) \times d_i \equiv 0 \pmod{10}$$
4. An exact normalized ISBN match in search bypasses heuristic ranking and is pinned to Rank 1 with an artificial RRF score boost of `+10.0`.

## 8.3 Dense Semantic Retrieval Channel
The semantic retrieval channel converts the patron's natural language inquiry into a 384-dimensional dense vector using the `all-MiniLM-L6-v2` transformer model:
$$\vec{q} = \text{Encode}(\text{query})$$
The engine scans active monograph embeddings, deserializing binary BLOBs via `numpy.frombuffer(blob, dtype=np.float32)` and computing cosine similarity:
$$\text{CosineSimilarity}(\vec{q}, \vec{d}) = \frac{\vec{q} \cdot \vec{d}}{\|\vec{q}\| \|\vec{d}\|}$$
Candidate monographs exceeding the minimum similarity threshold are ranked and selected.

## 8.4 Reciprocal Rank Fusion (RRF) Formulation
To combine dense semantic similarity with exact lexical precision, Athenaeum executes two parallel candidate retrieval channels and fuses their ranked outputs using Reciprocal Rank Fusion ($k = 60.0$):

$$\text{RRF\_Score}(d) = \sum_{m \in \{\text{lexical}, \text{semantic}\}} \frac{1}{k + r_m(d)}$$

Where $r_m(d)$ represents the 1-based rank of monograph $d$ in retrieval channel $m$. If a book appears in both channels, its scores reinforce each other. Ties are broken deterministically by:
1. Exact ISBN Match (+100.0 score boost)
2. Exact Title Match (+10.0 score boost)
3. Calculated RRF Score
4. Monograph ID ASC

---

# Chapter 9 — AI and Machine Learning Architecture

## 9.1 The Five Architectural AI Pillars
Athenaeum's intelligence layer is structured around five foundational pillars:
1. **Pillar 1: Knowledge Representation**: Hierarchical Subject $\rightarrow$ Topic $\rightarrow$ Concept DAG associating academic monographs with conceptual nodes.
2. **Pillar 2: Search-Based Conceptual Navigation**: Multi-level concept search enabling patrons to discover prerequisites and related fields.
3. **Pillar 3: Intelligent Librarian Agent**: Tool-calling conversational agent with bounded history, coreference resolution, and anti-hallucination guardrails.
4. **Pillar 4: Multi-Model Evaluation Studio**: Side-by-side prompt auditing across Gemini, OpenAI, and Local Deterministic models with empirical metrics for latency, token consumption, and factual grounding overlap.
5. **Pillar 5: Grounded RAG Assistant**: Retrieval-augmented generation with verifiable structured citations linked to physical copies and library policies.

## 9.2 Complete AI Copilot Execution Trace

```mermaid
sequenceDiagram
    autonumber
    actor Patron as Student Patron
    participant UI as AICopilotDrawer.tsx
    participant API as /api/v1/copilot/chat
    participant Agent as copilot_agent.py
    participant Tool as Tool Dispatcher
    participant DB as SQLite Relational Database
    participant LLM as External Gemini / Deterministic Fallback

    Patron->>UI: Types: "What books do I have on loan and can I renew them?"
    UI->>API: POST /copilot/chat {message, history: [...]}
    API->>API: Verify HttpOnly Session Cookie (Extract User ID: 5, Role: Student)
    API->>Agent: process_chat_inquiry(db, user, message, history)
    
    Agent->>Agent: Parse message for coreference and intents
    Note over Agent: Detects patron loan inquiry intent
    Agent->>Tool: tool_get_patron_loans(db, patron_id=5)
    Tool->>DB: SELECT * FROM loans WHERE user_id = 5 AND status = 'active'
    DB-->>Tool: Return Loan Record (Book: "Design Patterns", Due: In 3 days, Renewals: 1/2)
    Tool-->>Agent: Injects formatted loan facts into context block
    
    Agent->>Tool: tool_lookup_library_policy(topic="renewals")
    Tool-->>Agent: Injects policy rule: "Students may renew active loans up to 2 times..."
    
    Agent->>Agent: Construct Grounded Prompt with Anti-Injection Delimiters
    Agent->>LLM: Dispatch Prompt with System Context & Injected Facts
    
    alt Live Gemini Key Configured
        LLM-->>Agent: "You currently have 1 active loan: 'Design Patterns', due in 3 days. Since you have only used 1 of your 2 permitted renewals, you are eligible to renew this book through your Student Loans dashboard."
    else Offline / Deterministic Fallback
        Agent->>Agent: Deterministic Template Synthesis
        Note over Agent: Formats facts into structured deterministic reply
    end

    Agent->>Agent: Parse and append StructuredCitation(source_type="policy", title="Loan Renewal Policy", action_link="/student/loans")
    Agent-->>API: EnhancedCopilotResponse(reply, tool_calls, citations)
    API-->>UI: 200 OK JSON Response
    UI-->>Patron: Displays response with clickable action pill to Renew Loan
```

## 9.3 Model Comparison Studio Metric Formats
In `backend/app/services/ai_comparison.py`, models are evaluated against standardized quantitative metrics:
1. **Response Latency ($ms$)**: High-resolution wall-clock duration measured via `time.perf_counter()`.
2. **Token Quantification**: Estimates prompt tokens, completion tokens, and total token throughput.
3. **Factual Grounding Score ($0.0 \text{ to } 1.0$)**: Computes unigram and bigram token overlap between the generated response text and verified ground-truth policy text:
$$\text{Grounding Score} = \frac{|\text{Tokens}_{\text{generated}} \cap \text{Tokens}_{\text{policy}}|}{|\text{Tokens}_{\text{generated}}|}$$

---

# Chapter 10 — Academic Research Discovery

## 10.1 Multi-Source Scholarly Integration
Athenaeum integrates three major scholarly literature providers via asynchronous HTTPX clients (`backend/app/services/research/`):
1. **OpenAlex**: Searches over 250 million global scientific works, retrieving authors, affiliations, publication year, open-access PDF URLs, and citation counts.
2. **arXiv Export API**: Queries pre-print manuscripts in computer science, mathematics, and physics, parsing XML Atom feeds into standardized bibliographic objects.
3. **Crossref Metadata API**: Queries publisher-registered Digital Object Identifiers (DOIs), resolving publication venues, peer-review metadata, and ISSNs.

## 10.2 Deduplication & Normalization
Incoming research results are normalized into a unified schema:
- **DOI Normalization**: DOIs are stripped of URL prefixes and lowercased (`10.1145/...`).
- **Deduplication Engine**: When identical DOIs are returned from multiple providers (e.g., both Crossref and OpenAlex), the aggregator merges the records, preserving the open-access PDF link from OpenAlex while retaining the publisher metadata from Crossref.
- **Resilient Timeouts**: All external HTTP queries enforce a strict 5.0-second timeout. If one provider fails or times out, the aggregator returns results from the remaining providers without crashing the patron interface.

---

# Chapter 11 — Circulation and Library Operations

## 11.1 The Complete Loan Lifecycle
Circulation operations follow strict institutional rules:
- **Borrowing Quotas**: Students may borrow up to 5 items simultaneously; Faculty may borrow up to 10 items.
- **Loan Durations**: Standard student loans are 14 days; Faculty loans are 30 days; Course Reserve loans are 2 hours.
- **Self-Service Renewals**: Patrons may renew an active loan up to 2 times, provided no pending hold has been placed by another patron.

## 11.2 Priority Hold Queue & Automatic Allocation
When all physical copies of a monograph are checked out, patrons may place a Hold:
1. Holds are inserted into `book_holds` with an incrementing `queue_position` (FIFO ordering).
2. When any patron returns a copy of that monograph, `loans.py` triggers `on_book_copy_returned()`.
3. The system queries the oldest pending hold for that title, transitions its status to `ready_for_pickup`, and sets a 48-hour pickup expiration window.
4. The physical copy status changes to `reserved`, preventing other patrons or desk librarians from checking it out to walk-in patrons.

## 11.3 Cryptographic QR Book Collection
To facilitate touchless, verified physical checkout:
1. A patron with a `ready_for_pickup` hold generates a QR token via `/api/v1/circulation/qr-collection/generate`.
2. The server creates a 32-byte cryptographic token with a 15-minute expiration timestamp.
3. The patron displays the QR code at the library counter.
4. The desk librarian scans the QR code. The server verifies the token signature, matches the reserved copy barcode, marks the token consumed, marks the hold fulfilled, and automatically creates an active Loan record.

## 11.4 Lost & Damaged Inventory Processing
Physical copy integrity is managed through the Copy Status Modal (`CopyStatusModal.tsx`):
- Librarians can transition copy conditions between `good`, `fair`, `poor`, `damaged`, and `lost`.
- Marking a copy `lost` or `damaged` removes it from active circulation, logs an `InventoryEvent` audit record, and triggers an acquisition demand alert if total available copies fall below minimum safety thresholds.

---

# Chapter 12 — Teacher and Course Management

## 12.1 Course Reading Lists & Syllabi
Instructors manage academic courses via the Teacher Portal (`TeacherPortal.tsx`):
- Instructors create courses specifying course code, title, and academic term.
- Instructors search the library catalog to link required and recommended reading monographs.
- Instructors can upload course syllabi in PDF/text formats, which are stored securely on the filesystem and summarized in the course overview.

## 12.2 Course Reserves Policy Enforcement
To guarantee equitable access to high-demand curriculum materials, instructors can flag linked monographs as **Course Reserves**:
- Target physical copies are marked with the `course_reserve` flag.
- The circulation engine automatically overrides standard borrowing durations, enforcing a strict 2-hour in-library use limit.
- Self-service online renewals are disabled for course reserve copies, ensuring the volume returns to the reserve shelf for other students in the cohort.

---

# Chapter 13 — Spatial Navigation & Interactive Floor Plans

## 13.1 Spatial Schema & Topological Graph
The library physical plant is modeled as a topological graph across multiple floors:
- **`LibraryFloor`**: Represents physical elevation (Ground Floor 0, First Floor 1, etc.) with SVG canvas dimensions ($1000 \times 700$).
- **`FloorPlan`**: Version-controlled architectural layout linked to floors with status `draft`, `published`, or `archived`.
- **`SpatialResourceMapping`**: Georeferences individual study seats, rooms, and book stacks to Cartesian coordinates $(x, y)$ on a specific floor layout.
- **`WayfindingNode`**: Topological graph vertices categorized as `entrance`, `corridor`, `stairwell`, `elevator`, or `destination`.
- **`WayfindingEdge`**: Bidirectional graph edges with Euclidean distance weights:
$$d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}$$

## 13.2 Dijkstra Shortest-Path Traversal
When a patron requests wayfinding directions to a study seat, room, or book collection counter:
1. The system resolves the resource's spatial coordinates from `spatial_resource_mappings`.
2. The nearest destination waypoint node is identified.
3. The navigation engine (`backend/app/services/spatial.py`) executes Dijkstra's algorithm using Python's `heapq` priority queue, computing the globally optimal shortest path from the floor entrance to the destination.
4. The server returns a `WayfindingRouteResponse` containing total path distance, an SVG polyline path string, and structured turn-by-turn navigation instructions (e.g., *"Proceed 15 meters down the North Corridor, turn right at the Reference Desk"*).

---

# Chapter 14 — Intelligence and Analytics

## 14.1 Executive KPI Snapshots
The Librarian Intelligence Centre aggregates real-time operational metrics:
- **Active Loans & Circulation Velocity**: Daily checkout and return rates segmented by academic discipline.
- **Collection Turnover Rate**: Ratio of total annual checkouts to total monograph holdings:
$$\text{Turnover Rate} = \frac{\text{Total Checkouts}}{\text{Total Catalog Holdings}}$$
- **Zero-Borrow Inventory**: Identification of monographs that have experienced zero checkout events over the past 365 days, supporting data-driven weeding or stack relocation decisions.

## 14.2 Holt-Winters Time-Series Demand Forecasting
To anticipate upcoming circulation spikes (e.g., midterms, finals week), the intelligence engine implements exponential smoothing and Holt-Winters forecasting over historical daily checkout logs:
- **Level Smoothing ($L_t$)**:
  $$L_t = \alpha Y_t + (1 - \alpha)(L_{t-1} + T_{t-1})$$
- **Trend Smoothing ($T_t$)**:
  $$T_t = \beta (L_t - L_{t-1}) + (1 - \beta)T_{t-1}$$
- **Forecast Generation**:
  $$\hat{Y}_{t+m} = L_t + m T_t$$
Generates 30-day projected checkout volumes with 95% confidence intervals, visualized in interactive frontend trend charts.

## 14.3 Automated Acquisition Workflows
The acquisition engine calculates an automated **Acquisition Pressure Score** for titles with high demand:
$$\text{Score} = (W_{\text{hold}} \times \text{Active Hold Count}) + (W_{\text{velocity}} \times \text{Circulation Velocity}) - (W_{\text{avail}} \times \text{Available Copies})$$
Titles exceeding the critical threshold automatically populate the Acquisition Orders table with recommended purchase quantities.

---

# Chapter 15 — Detailed API Architecture & Schema Reference

Below is an exhaustive technical specification of Athenaeum's primary REST endpoints across all domains:

### 15.1 Authentication Router (`backend/app/routers/auth.py`)

#### `POST /api/v1/auth/register`
- **Purpose**: Enables self-registration for student patrons.
- **Authorization**: Public unauthenticated.
- **Request Body (`UserRegisterRequest`)**:
  ```json
  {
    "email": "student@university.edu",
    "username": "johndoe",
    "password": "SecurePassword123!",
    "full_name": "John Doe"
  }
  ```
- **Validation Rules**: `email` must be valid format, `username` must be alphanumeric (3-30 chars), `password` must be $\ge 12$ chars.
- **Response (`UserResponse`, HTTP 201 Created)**:
  ```json
  {
    "id": 42,
    "email": "student@university.edu",
    "username": "johndoe",
    "role": "student",
    "full_name": "John Doe",
    "is_active": true,
    "created_at": "2026-11-08T12:00:00Z"
  }
  ```
- **Error Responses**: HTTP 400 Bad Request if email/username already registered, HTTP 422 if password $< 12$ characters.

#### `POST /api/v1/auth/login`
- **Purpose**: Authenticates patrons using either email or username with password, issuing an HttpOnly JWT cookie.
- **Authorization**: Public unauthenticated.
- **Request Body (`LoginRequest`)**:
  ```json
  {
    "identifier": "student@university.edu",
    "password": "SecurePassword123!"
  }
  ```
- **Response Headers**: `Set-Cookie: access_token=eyJhbGci...; Path=/; HttpOnly; SameSite=Lax`
- **Response Body (`LoginResponse`, HTTP 200 OK)**:
  ```json
  {
    "message": "Login successful",
    "user": {
      "id": 42,
      "email": "student@university.edu",
      "username": "johndoe",
      "role": "student",
      "full_name": "John Doe"
    }
  }
  ```
- **Error Responses**: HTTP 401 Unauthorized for invalid credentials.

#### `POST /api/v1/auth/forgot-password`
- **Purpose**: Dispatches password recovery link over SMTP.
- **Request Body (`ForgotPasswordRequest`)**: `{"email": "student@university.edu"}`
- **Response (HTTP 200 OK)**: `{"message": "If this email is registered, password reset instructions have been sent."}`

#### `POST /api/v1/auth/reset-password`
- **Purpose**: Verifies SHA-256 token and establishes new bcrypt password.
- **Request Body (`ResetPasswordRequest`)**:
  ```json
  {
    "token": "raw-32-byte-token-from-email",
    "new_password": "NewSecurePassword123!"
  }
  ```
- **Response (HTTP 200 OK)**: `{"message": "Password successfully reset. You may now log in."}`
- **Error Responses**: HTTP 400 Bad Request if token is invalid, expired, or already used.

### 15.2 Catalogue & Semantic Router (`backend/app/routers/catalogue.py`, `semantic.py`)

#### `GET /api/v1/semantic/hybrid-search`
- **Purpose**: Reciprocal Rank Fusion blending lexical and dense vector search.
- **Query Parameters**:
  - `q` (string, required): Search query (e.g., `"deep learning"`).
  - `page` (int, default: 1): Page number.
  - `page_size` (int, default: 10): Items per page.
  - `category` (string, optional): Filter by subject category.
- **Response Body (`HybridSearchResponse`, HTTP 200 OK)**:
  ```json
  {
    "items": [
      {
        "id": 12,
        "isbn": "9780262035613",
        "title": "Deep Learning",
        "author": "Ian Goodfellow, Yoshua Bengio, Aaron Courville",
        "category": "Computer Science",
        "publication_year": 2016,
        "available_copies": 2,
        "total_copies": 3,
        "lexical_rank": 1,
        "semantic_rank": 2,
        "rrf_score": 0.0325,
        "semantic_similarity": 0.842
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10,
    "total_pages": 1,
    "query": "deep learning"
  }
  ```

### 15.3 Circulation & Holds Router (`backend/app/routers/holds.py`, `circulation_ops.py`)

#### `POST /api/v1/holds`
- **Purpose**: Places a patron hold on an exhausted monograph.
- **Authorization**: Student, Teacher, or Librarian.
- **Request Body (`HoldCreateRequest`)**: `{"book_id": 12}`
- **Response Body (`HoldResponse`, HTTP 201 Created)**:
  ```json
  {
    "id": 8,
    "user_id": 42,
    "book_id": 12,
    "status": "pending",
    "queue_position": 1,
    "placed_at": "2026-11-08T14:30:00Z",
    "expires_at": null
  }
  ```

#### `POST /api/v1/circulation-ops/qr-collection/generate`
- **Purpose**: Generates a 15-minute cryptographic collection token for an approved hold.
- **Request Body**: `{"hold_id": 8}`
- **Response Body (HTTP 200 OK)**:
  ```json
  {
    "token": "b7f9a12c4d8e0f...",
    "hold_id": 8,
    "book_title": "Deep Learning",
    "expires_at": "2026-11-08T14:45:00Z",
    "qr_svg_data": "data:image/svg+xml;utf8,..."
  }
  ```

#### `POST /api/v1/circulation-ops/qr-collection/verify`
- **Purpose**: Desk librarian scans patron QR token to fulfill hold into an active loan.
- **Authorization**: Librarian or Admin.
- **Request Body**: `{"token": "b7f9a12c4d8e0f...", "copy_barcode": "BC-100234"}`
- **Response Body (HTTP 200 OK)**:
  ```json
  {
    "message": "Hold fulfilled and loan activated successfully.",
    "loan_id": 55,
    "patron_name": "John Doe",
    "due_date": "2026-11-22"
  }
  ```

### 15.4 Intelligence & Forecasting Router (`backend/app/routers/intelligence.py`)

#### `GET /api/v1/intelligence/snapshot`
- **Purpose**: Executive dashboard KPIs for collection management.
- **Authorization**: Librarian or Admin.
- **Response Body (`IntelligenceSnapshotResponse`, HTTP 200 OK)**:
  ```json
  {
    "total_monographs": 1240,
    "total_copies": 3480,
    "active_loans": 412,
    "pending_holds": 28,
    "turnover_rate": 2.45,
    "zero_borrow_count": 86,
    "forecasted_30d_demand": 520
  }
  ```

---

# Chapter 16 — Installation and Environment Configuration

## 16.1 System Requirements
- **Operating System**: Windows 10/11 (PowerShell), Ubuntu 22.04+, or macOS 13+.
- **Python**: Version `3.10` or higher (`3.11.x` recommended).
- **Node.js**: Version `18.x` or higher (`20.x` LTS recommended).

## 16.2 Step-by-Step Local Setup
Refer to [INSTALLATION.md](../INSTALLATION.md) for the complete executable commands. In brief:
1. Clone the repository: `git clone <repo_url> && cd AI-Library-Management-System`.
2. Create Python virtual environment: `python -m venv backend\venv`.
3. Activate environment: `.\backend\venv\Scripts\Activate.ps1`.
4. Install backend dependencies: `pip install -r backend\requirements.txt`.
5. Copy environment file: `Copy-Item .env.example .env`.
6. Install frontend dependencies: `npm --prefix frontend install`.
7. Launch backend: `python -m uvicorn backend.app.main:app --reload`.
8. Launch frontend: `npm --prefix frontend run dev`.

---

# Chapter 17 — Testing and Quality Assurance

## 17.1 Test Strategy & Test Suite Architecture
Athenaeum maintains a comprehensive automated testing harness under `backend/tests/` comprising 27 test suites and 395 individual assertions.

### 17.1.1 Verified Test Execution Snapshot (Snapshot Date: 2026-11-08)
```
393 passed, 2 skipped, 9 warnings in 148.61s (0:02:28)
```
- **0 Failures**: Zero regressions across all functional domains.
- **2 Skips**: Windows non-administrative symlink permission assertions (`test_database_protection.py:158`, `test_seed_safety.py:125`). These are environmental OS constraints when running without elevated UAC privileges, not application defects.
- **Test Isolation**: In `backend/tests/conftest.py`, the test environment forces `LLM_PROVIDER="fallback"` and in-memory SQLite instances (`sqlite:///:memory:`), ensuring that tests never make billable cloud API calls or mutate on-disk production databases.

## 17.2 Frontend Production Compilation
The client application is tested via TypeScript compiler checks and Vite Rollup bundler builds:
```
npm --prefix frontend run build
✓ 147 modules transformed.
dist/index.html                   0.62 kB │ gzip:   0.38 kB
dist/assets/index-DWCk_P_x.css   40.61 kB │ gzip:   8.12 kB
dist/assets/index-BfvhFB8z.js   553.08 kB │ gzip: 147.07 kB
✓ built in 1.22s
```

---

# Chapter 18 — Security and Privacy

## 18.1 Defense-in-Depth Implementation
1. **Cryptographic Key Segregation**: Distinct, validated secrets for `JWT_SECRET_KEY` and `SPACES_QR_SECRET_KEY`.
2. **Timing-Safe Operations**: Authentication and reset token verifications utilize constant-time comparison algorithms to prevent side-channel timing attacks.
3. **Session Hardening**: HttpOnly, SameSite cookies mitigate client-side script hijacking.
4. **Patron Data Privacy**: AI Copilot tools strictly scope database queries to the authenticated patron's user ID, preventing cross-patron record leakage.

---

# Chapter 19 — Deployment and Operational Considerations

## 19.1 Production Deployment Architecture
In a production university deployment:
- **Reverse Proxy**: Nginx or Caddy terminating TLS (HTTPS) on port 443, proxying API requests to Uvicorn workers on port 8000 and serving static frontend build assets from `frontend/dist/`.
- **Database Engine**: Transition from SQLite to PostgreSQL 16 by updating `DATABASE_URL` in `.env` (e.g., `postgresql+psycopg2://user:pass@localhost:5432/athenaeum`).
- **Process Supervision**: Systemd or Docker containers managing Uvicorn worker restarts and log rotation.

---

# Chapter 20 — Known Limitations and Future Roadmap

## 20.1 Documented System Limitations
1. **Biometric & Financial Processing**: Biometric identity authentication (ADV-04) and real payment gateway fine processing (ADV-05) remain excluded pending separate institutional regulatory approval.
2. **Minute-Precision Course Reserves**: The `loans.due_date` column is modeled as a `Date` object; short 2-hour reserve loans set same-day expiration boundaries rather than minute-precision countdown timers.
3. **External API Quotas**: External academic queries to OpenAlex, arXiv, and Crossref depend on third-party API availability and rate limits.

---

# Chapter 21 — Team Developer Guide

## 21.1 End-to-End Tutorial: Adding a New Subsystem
To illustrate the architectural lifecycle for onboarding developers, below is the exact sequence for implementing a hypothetical *"Book Review"* capability:

### Step 1: Define Relational Entity (`backend/app/models.py`)
```python
class BookReview(Base):
    __tablename__ = "book_reviews"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

### Step 2: Create Pydantic Validation Schemas (`backend/app/schemas.py`)
```python
class BookReviewCreate(BaseModel):
    book_id: int
    rating: int = Field(ge=1, le=5, description="Star rating between 1 and 5")
    comment: Optional[str] = Field(None, max_length=1000)

class BookReviewResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    rating: int
    comment: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```

### Step 3: Implement Service Logic (`backend/app/services/reviews.py`)
```python
def create_review_service(db: Session, user_id: int, payload: BookReviewCreate) -> BookReview:
    with atomic_write(db):
        review = BookReview(
            user_id=user_id,
            book_id=payload.book_id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(review)
        db.flush()
        db.refresh(review)
        return review
```

### Step 4: Expose Asynchronous Router (`backend/app/routers/reviews.py`)
```python
router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.post("", response_model=BookReviewResponse, status_code=status.HTTP_201_CREATED)
def post_review(
    payload: BookReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_review_service(db=db, user_id=current_user.id, payload=payload)
```

### Step 5: Mount Router in `backend/app/main.py`
```python
from app.routers import reviews
app.include_router(reviews.router, prefix="/api/v1")
```

### Step 6: Write Automated Regression Test (`backend/tests/test_reviews.py`)
```python
def test_post_book_review(client, authenticated_student_cookie):
    response = client.post(
        "/api/v1/reviews",
        json={"book_id": 1, "rating": 5, "comment": "Seminal textbook on algorithms."},
        cookies=authenticated_student_cookie,
    )
    assert response.status_code == 201
    assert response.json()["rating"] == 5
```


---

# Chapter 10 — Autonomous ReAct Agent Architecture & The 10-Tool Arsenal

## 10.1 ReAct Reasoning and Tool Dispatch Engine
The Athenaeum Autonomous Copilot uses a Reasoning + Acting (ReAct) paradigm powered by Google Gemini (with deterministic offline fallback). Rather than behaving as a static text completion bot, the agent parses patron intent, formulates hypotheses, executes database or external API tools, inspects intermediate tool outputs, and synthesizes a grounded response with structured UI action cards.

```mermaid
sequenceDiagram
    autonumber
    actor Patron as Student / Teacher Patron
    participant UI as AICopilotDrawer (React)
    participant Router as /api/knowledge/agent/chat
    participant Agent as CopilotAgent Orchestrator
    participant Tools as 10-Tool Arsenal
    participant Gemini as Gemini 3.1 Flash Lite / BYOK
    participant DB as SQLite WAL / Vector Index

    Patron->>UI: "Can you renew my overdue loan and book a study desk tomorrow?"
    UI->>Router: POST /api/knowledge/agent/chat (Bearer + X-Gemini-API-Key)
    Router->>Agent: execute_librarian_agent_rag(query, patron, history)
    Agent->>Gemini: Prompt + 10 Tool Declarations
    Gemini-->>Agent: ToolCall: check_personal_loans(patron_id=4)
    Agent->>Tools: execute(check_personal_loans)
    Tools->>DB: Query active patron loans
    DB-->>Tools: Loan #14 (Distributed Systems Engineering)
    Tools-->>Agent: Intermediate observation: Loan #14 eligible for renewal
    Agent->>Gemini: Intermediate Observation
    Gemini-->>Agent: ToolCall: renew_loan(loan_id=14)
    Agent->>Tools: execute(renew_loan)
    Tools->>DB: Advance due_date +14 days
    DB-->>Tools: Renewed successfully to 2026-11-23
    Tools-->>Agent: Success
    Agent->>Gemini: Intermediate Observation
    Gemini-->>Agent: ToolCall: reserve_study_seat(desk_id=12, start_time="...")
    Agent->>Tools: execute(reserve_study_seat)
    Tools->>DB: Create reservation entry
    DB-->>Tools: Reservation #88 confirmed
    Tools-->>Agent: Reservation confirmed
    Agent->>Gemini: Synthesize final user response
    Gemini-->>Agent: Final patron response with structured actions
    Agent-->>Router: EnhancedCopilotResponse (answer, agent_actions, cards, citations)
    Router-->>UI: Render message bubble + Interactive Action Cards
```

## 10.2 The 10-Tool Arsenal Specification

| # | Tool Name | Scope & Purpose | Required Arguments & Types | Permission Boundary | Service Function |
|---|---|---|---|---|---|
| **1** | `search_catalogue` | Hybrid lexical/dense vector search over library holdings. | `query` (str), `limit` (int = 5) | Public / All Patrons | `catalogue_service.hybrid_search` |
| **2** | `get_book_details` | Detailed monograph metadata, copy breakdown, and shelf location. | `book_id` (int) | Public / All Patrons | `catalogue_service.get_book_by_id` |
| **3** | `check_personal_loans` | Retrieves active borrowings, due dates, and renewal eligibility. | *None* (Bound to `current_user.id`) | Authenticated Patron Only (Multi-tenant isolation) | `loans_service.get_user_loans` |
| **4** | `renew_loan` | Extends eligible physical monograph borrowings by standard loan term. | `loan_id` (int) | Authenticated Patron (Self-owned only) | `loans_service.renew_loan` |
| **5** | `check_seat_availability` | Queries vacant study carrels and group rooms by floor/date. | `floor` (int), `target_date` (str YYYY-MM-DD) | All Patrons | `space_service.get_available_spaces` |
| **6** | `reserve_study_seat` | Autonomously books a study desk or collaborative room. | `space_id` (int), `start_time` (ISO), `duration_hours` (int) | Authenticated Patron (Student/Teacher quota) | `space_service.create_reservation` |
| **7** | `get_patron_clearance` | Evaluates zero-fine non-punitive graduation/term clearance. | `student_id` (int) | Self (Student) or Librarian / Admin | `circulation_ops_service.get_clearance` |
| **8** | `get_course_reserves` | Fetches academic course syllabus reading lists & reserved copies. | `course_code` (str) | Public / All Patrons | `courses_service.get_reserves_by_code` |
| **9** | `search_preprints` | Live federated scholarly retrieval over arXiv, OpenAlex & Crossref. | `query` (str), `max_results` (int = 5) | Public / All Patrons | `academic_research_service.search_papers` |
| **10** | `calculate_two_week_demand_forecast` | 14-day Holt-Winters time-series circulation demand projection. | *None* | Librarian / Teacher / System | `forecasting_service.get_two_week_forecast` |

---

# Chapter 11 — Multimodal Omnichannel Research Discovery

## 11.1 Supported Media Ingestion Formats
Athenaeum integrates full multimodal research discovery via the Gemini 3.5 Flash Lite engine. Patrons can submit non-textual research inputs directly through the drag-and-drop / clipboard-paste modal:

1. **Spoken Audio & Lecture Clips** (`.mp3`, `.wav`, `.m4a`, `.webm`, `.ogg`):
   - Ingested via browser Web Audio API / `MediaRecorder` or file upload up to 25MB.
   - Decoded and tokenized directly by Gemini multimodal audio layers.
   - Extracts verbatim transcripts, speaker tone, core academic queries, and thematic concepts.
2. **Academic Research Papers** (`.pdf`):
   - Parsed with `pypdf` stream processing + Gemini document comprehension.
   - Automatically extracts abstract, methodology, LaTeX mathematical formulas, and bibliographical citations.
3. **Microsoft Office Documents** (`.docx`, `.pptx`):
   - Word documents decomposed via `python-docx` into paragraph and table trees.
   - PowerPoint slides decomposed via `python-pptx` extracting slide titles, bullet points, speaker notes, and diagram annotations.
4. **Handwritten Whiteboard Math & Diagrams** (`.png`, `.jpg`, `.jpeg`, `.webp`):
   - Direct vision analysis extracting LaTeX mathematical equations (e.g. `\nabla \times \mathbf{E} = -\frac{\partial \mathbf{B}}{\partial t}`).
   - Optical character recognition of handwritten whiteboard notes.
   - Structural diagram flow extraction (DAGs, circuit schematics, UML models).

## 11.2 Dual-Index Retrieval Pipeline
Upon extracting academic topics and terminology from uploaded media, Athenaeum executes parallel retrieval:
- **Local Physical Monograph Retrieval**: Queries local library catalog using 384-dimensional dense semantic vectors combined with BM25 lexical ranking.
- **Global Open-Access Scholarly Retrieval**: Queries arXiv preprints and OpenAlex open metadata API, deduplicating by DOI/arXiv ID.

---

# Chapter 12 — Bring-Your-Own-Key (BYOK) AI Architecture

## 12.1 Student & Teacher Privacy Model
To provide students and faculty complete control over AI quotas, model choices, and data privacy, Athenaeum implements a zero-trust **Bring-Your-Own-Key (BYOK)** pattern:

```mermaid
flowchart LR
    subgraph Client ["Client Browser (Student/Teacher)"]
        INPUT["Patron Profile Modal\nEnter Gemini Key (AIzaSy...)"]
        LS[("localStorage\npatron_custom_gemini_key")]
        HTTP["apiFetch Wrapper\nX-Gemini-API-Key Header"]
        INPUT --> LS
        LS --> HTTP
    end

    subgraph Backend ["Athenaeum FastAPI Server"]
        MW["Security Middleware\n(CSRF & Origin Whitelist)"]
        ROUTER["Routers\n/api/copilot/chat\n/api/knowledge/agent/chat\n/api/research/vision-search"]
        RESOLVER{"Key Resolution\nHierarchy"}
        
        HTTP --> MW --> ROUTER --> RESOLVER
        
        RESOLVER -->|"1. Patron BYOK Key Present"| LIVE_KEY["Use Patron Key\n(Bypasses Campus Quota)"]
        RESOLVER -->|"2. No Patron Key"| ENV_KEY["Use Campus GEMINI_API_KEY\n(Institutional Default)"]
        RESOLVER -->|"3. Offline / No Keys"| FALLBACK["Deterministic Offline Engine\n(Factual DB Synthesis)"]
    end

    subgraph Google ["Google Generative AI"]
        API["Gemini 3.5 Flash Lite API"]
        LIVE_KEY --> API
        ENV_KEY --> API
    end
```

## 12.2 Security Guarantees
- **No Plaintext Key Storage**: Personal API keys are stored exclusively in the patron's browser `localStorage` and sent over TLS. They are never written to the SQLite database or persisted in server logs.
- **Instant Validation**: Patrons can click **"⚡ Test Key"** in the Patron Profile Modal to execute a sub-second live verification probe via `POST /api/copilot/verify-key`.
- **Immediate Reversion**: Clicking **"Clear & Use Default"** instantly removes the personal key and reverts the patron to the campus institutional allocation.

---

# Chapter 13 — Non-Punitive Academic Circulation & Physical Logistics

## 13.1 Non-Punitive Clearance System
In accordance with ethical academic library standards, Athenaeum implements a strictly non-punitive zero-fine circulation policy:
- Overdue monographs do not accrue financial penalties or late fines.
- Circulation privileges are temporarily paused only while physical items remain unreturned past due dates.
- Graduation and end-of-term clearance certificates (`/api/circulation/clearance/certificate/{student_id}`) are generated as cryptographic SHA-256 verified digital credentials certifying complete return of institutional physical assets.

## 13.2 Rapid QR Return Kiosks
Patrons return books at contactless kiosks using encrypted QR collection passes (`/api/circulation/returns/qr-process`). Scanning the physical book barcode or patron token instantly discharges the loan, transitions the copy back to available inventory, and issues an immutable digital receipt.
