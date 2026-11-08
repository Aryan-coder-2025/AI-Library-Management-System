# Athenaeum: System Architecture Specification

## 1. Executive Architecture Summary

**Athenaeum** is an enterprise-grade, AI-augmented academic library management and intelligence platform. It bridges traditional physical circulation lifecycles with modern digital discovery, spatial wayfinding, and an agentic multi-pillar artificial intelligence engine.

The platform is architected around a decoupled client-server paradigm:
- **Client Tier**: Single Page Application (SPA) built with React 19, TypeScript 5.8, and Vite 5.4, utilizing atomic component isolation and responsive glassmorphic design systems.
- **Application Tier**: High-throughput asynchronous REST API built on FastAPI 0.110+ (Starlette / Pydantic v2), organized into specialized modular domain routers and stateless domain service engines.
- **Persistence Tier**: Relational data store managed via SQLAlchemy 2.0 ORM with Alembic schema versioning, strictly isolating transactional workflows, foreign key constraints, and spatial geometries.
- **Intelligence & AI Tier**: Multi-provider LLM abstraction layer (Google Gemini 3.1, OpenAI GPT-4o, Local Ollama, and Deterministic Fallback), dense semantic vector retrieval via SentenceTransformers (`all-MiniLM-L6-v2`, 384 dimensions), Reciprocal Rank Fusion (RRF), and a tool-calling Librarian Agent.

```mermaid
graph TB
    subgraph Client ["Client Presentation Tier (React 19 + TypeScript + Vite)"]
        UI_Guest["Public Guest OPAC"]
        UI_Student["Student Discovery & Workspace"]
        UI_Teacher["Faculty & Teacher Portal"]
        UI_Librarian["Librarian Circulation & Intelligence"]
        UI_Admin["Administrative Studio & Config"]
    end

    subgraph Security ["Security & Gateway Middleware"]
        CORS["CORS Policy Validation"]
        RateLimit["Per-Patron Rate Limiter"]
        JWTCookie["HttpOnly Signed JWT Cookie Session"]
        AuditLog["Security Audit Logging"]
    end

    subgraph API ["Application Layer (FastAPI Asynchronous Engine)"]
        R_Auth["Auth & Recovery Router"]
        R_Catalogue["Catalogue & Search Router"]
        R_Circulation["Circulation & QR Router"]
        R_Courses["Course Reserves & Syllabi Router"]
        R_Research["Academic Aggregator Router"]
        R_Spaces["Study Space & Booking Router"]
        R_Spatial["Spatial Layout & Wayfinding Router"]
        R_Intel["Intelligence & Analytics Router"]
        R_Copilot["Agentic AI Copilot Router"]
    end

    subgraph Services ["Domain Service Layer"]
        S_Email["Transactional SMTP Service"]
        S_Holds["Hold Queue & Allocation Engine"]
        S_QR["Cryptographic QR Engine"]
        S_Research["External Academic Aggregator"]
        S_Spatial["Dijkstra Wayfinding Engine"]
        S_Forecast["Holt-Winters Demand Forecaster"]
        S_Agent["Librarian Copilot Tool Dispatcher"]
        S_Hybrid["Dense/Lexical Hybrid Search Engine"]
    end

    subgraph Data ["Persistence & Vector Tier"]
        DB[(SQLite / PostgreSQL Engine)]
        Vectors["Dense Vector Store (384-dim BLOBs)"]
        Knowledge["Hierarchical Knowledge Graph"]
    end

    subgraph External ["External Integration Tier"]
        OpenAlex["OpenAlex API"]
        ArXiv["arXiv Export API"]
        Crossref["Crossref Metadata API"]
        GeminiAPI["Google Gemini Live API"]
        OllamaEngine["Local Ollama Inference"]
        SMTPRelay["University SMTP Relay"]
    end

    Client --> Security
    Security --> API
    API --> Services
    Services --> Data
    S_Research --> OpenAlex
    S_Research --> ArXiv
    S_Research --> Crossref
    S_Agent --> GeminiAPI
    S_Agent --> OllamaEngine
    S_Email --> SMTPRelay
```

---

## 2. Container-Level Architecture

The Athenaeum deployment model comprises five decoupled execution boundaries designed for resilience and local testability:

```mermaid
flowchart LR
    Browser["Patron Web Browser\n(Desktop / Mobile)"] -- "HTTPS / JSON\nHttpOnly Cookies" --> WebServer["Vite Frontend Server\n(Port 5173 / Production Nginx)"]
    WebServer -- "API Reverse Proxy\n/api/v1/*" --> BackendApp["FastAPI Uvicorn Worker\n(Port 8000)"]
    
    subgraph Backend_Process ["FastAPI Application Boundary"]
        BackendApp --> RouterDispatch["Router Dispatcher"]
        RouterDispatch --> ServiceLayer["Domain Services"]
        ServiceLayer --> ORM["SQLAlchemy 2.0 ORM"]
        ServiceLayer --> LocalAI["SentenceTransformers Engine\n(all-MiniLM-L6-v2)"]
    end

    ORM -- "Local Connection Pool\nPRAGMA foreign_keys = ON" --> RelationalDB[("Relational Database\nSQLite / Postgres")]
    ServiceLayer -- "Asynchronous HTTPS" --> ExternalLLM["Remote AI Providers\n(Google AI Studio / OpenAI)"]
    ServiceLayer -- "HTTP (11434)" --> LocalOllama["Ollama Daemon\n(Optional Local Engine)"]
    ServiceLayer -- "SMTP / TLS (587)" --> SMTP["SMTP Mail Relay"]
```

---

## 3. Frontend Component Architecture

The frontend application follows a strict modular structure centered on role-tailored workspaces and reactive state containment:

```mermaid
graph TD
    App["App.tsx\n(Core Layout & Session Lifecycle)"]
    
    subgraph Navigation ["Navigation & Modals"]
        Navbar["Navbar.tsx\n(Role Pills, Theme, Identity)"]
        CmdPal["CommandPalette.tsx\n(Global Cmd+K Shortcuts)"]
        PatronModal["PatronProfileModal.tsx\n(Profile & Password Update)"]
        TourModal["GuidedTourModal.tsx\n(Onboarding Flow)"]
        Bell["NotificationBell.tsx\n(Realtime Alerts)"]
    end

    subgraph AuthViews ["Authentication & Recovery"]
        SignIn["SignIn.tsx\n(Dual Email/Username Login)"]
        Register["Register.tsx\n(Student Self-Registration)"]
        Forgot["ForgotPassword.tsx\n(Reset Link Request)"]
        Reset["ResetPassword.tsx\n(Token Verification & Password Change)"]
    end

    subgraph PrimaryViews ["Primary Domain Dashboards"]
        StudentCat["StudentCatalogue.tsx\n(Hybrid Search & Filters)"]
        StudentLoans["StudentLoans.tsx\n(Active Loans, Holds & QR Collection)"]
        StudentSpaces["StudentSpaces.tsx\n(Seat & Room Booking)"]
        TeacherPort["TeacherPortal.tsx\n(Course Reading Lists & Syllabi)"]
        LibCirc["LibrarianCirculation.tsx\n(Desk Checkouts & Hold Processing)"]
        LibCat["LibrarianCatalogue.tsx\n(Monograph & Barcode Management)"]
        LibIntel["LibrarianIntelligenceCenter.tsx\n(Forecasting & Executive KPIs)"]
        AcademicRes["AcademicResearchDiscovery.tsx\n(OpenAlex, arXiv, Crossref)"]
        ModelStudio["ModelComparisonStudio.tsx\n(Side-by-Side Model Audits)"]
        KnowledgeExp["KnowledgeExplorer.tsx\n(Concept Graph Browser)"]
    end

    subgraph SpatialViews ["Spatial & Interactive Mapping"]
        FloorCanvas["FloorPlanCanvas.tsx\n(Interactive SVG Renderer)"]
        StudentFloor["StudentFloorPlan.tsx\n(Desk Selection & Wayfinding)"]
        LibFloorMgr["LibrarianFloorPlanManager.tsx\n(Visual Layout Editor)"]
    end

    subgraph Overlays ["Drawers & Modals"]
        CopilotDrawer["AICopilotDrawer.tsx\n(Interactive Multi-Turn RAG)"]
        BookModal["BookDetailModal.tsx\n(Metadata, Hold Trigger, Recommendations)"]
        QRModal["QRCodeModal.tsx / QRCollectionModal.tsx\n(Cryptographic Tokens)"]
        CopyModal["CopyStatusModal.tsx\n(Lost/Damaged Processing)"]
    end

    App --> Navigation
    App --> AuthViews
    App --> PrimaryViews
    PrimaryViews --> SpatialViews
    PrimaryViews --> Overlays
```

---

## 4. Backend Service Architecture

The backend implements a Clean Architecture layered service pattern. Routers handle HTTP protocol translation, request validation via Pydantic v2 schemas, and dependency injection, delegating all domain rules to stateless service modules:

```mermaid
classDiagram
    class RouterLayer {
        +auth_router
        +catalogue_router
        +circulation_ops_router
        +courses_router
        +holds_router
        +intelligence_router
        +knowledge_router
        +loans_router
        +research_router
        +spaces_router
        +spatial_router
    }

    class DomainServiceLayer {
        +acquisitions_service
        +ai_comparison_service
        +catalogue_service
        +copilot_agent_service
        +courses_service
        +email_service
        +embedding_service
        +forecasting_service
        +holds_service
        +intelligence_service
        +inventory_ops_service
        +qr_collection_service
        +research_aggregator_service
        +semantic_service
        +spatial_service
    }

    class DataAccessLayer {
        +crud_catalogue
        +crud_loans
        +crud_semantic
        +crud_spaces
        +crud_spatial
    }

    class PersistenceEntities {
        +User
        +Book
        +BookCopy
        +BookHold
        +BookCollectionToken
        +Loan
        +Course
        +CourseReserve
        +StudySeat
        +StudyRoom
        +Reservation
        +FloorPlan
        +WayfindingNode
    }

    RouterLayer --> DomainServiceLayer : invokes with Session
    DomainServiceLayer --> DataAccessLayer : queries / writes
    DataAccessLayer --> PersistenceEntities : maps relational state
```

---

## 5. Relational Database Architecture

Athenaeum manages 31 relational tables linked by rigorous foreign keys, check constraints, and performance indexes:

```mermaid
erDiagram
    users ||--o{ loans : "borrows"
    users ||--o{ reservations : "reserves"
    users ||--o{ book_holds : "places"
    users ||--o{ courses : "instructs"
    users ||--o{ password_reset_tokens : "requests"

    books ||--|{ book_copies : "contains"
    books ||--o{ book_holds : "queued_on"
    books ||--o{ course_reading_list_items : "referenced_in"
    books ||--o{ course_reserves : "reserved_for"
    books ||--o{ book_concepts : "categorized_by"

    book_copies ||--o{ loans : "circulates"
    book_copies ||--o{ inventory_events : "audits"
    book_copies ||--o{ book_collection_tokens : "reserved_via"

    courses ||--o{ course_reading_list_items : "specifies"
    courses ||--o{ course_reserves : "protects"

    library_floors ||--o{ study_zones : "subdivides"
    library_floors ||--o{ floor_plans : "visualizes"
    library_floors ||--o{ spatial_resource_mappings : "georeferences"
    library_floors ||--o{ wayfinding_nodes : "anchors"

    study_zones ||--o{ study_seats : "allocates"
    study_zones ||--o{ study_rooms : "encloses"

    study_seats ||--o{ reservations : "booked_as"
    study_rooms ||--o{ reservations : "booked_as"

    wayfinding_nodes ||--o{ wayfinding_edges : "connects_from"
    wayfinding_nodes ||--o{ wayfinding_edges : "connects_to"

    subjects ||--o{ topics : "hierarchical_parent"
    topics ||--o{ concepts : "hierarchical_parent"
    concepts ||--o{ book_concepts : "linked_with"
```

---

## 6. AI Copilot Request Lifecycle

When a patron submits an inquiry to the AI Assistant, the request executes through a deterministic, guardrailed multi-stage pipeline:

```mermaid
sequenceDiagram
    autonumber
    actor Patron as Patron Browser
    participant API as Copilot Router (/chat)
    participant Sec as Security & Rate Limiter
    participant Agent as Copilot Agent (copilot_agent.py)
    participant Tool as Tool Dispatcher
    participant DB as Relational Database
    participant LLM as External / Local LLM Provider

    Patron->>API: POST /api/copilot/chat {message, history}
    API->>Sec: Validate Rate Limits (25 req/min) & Auth Context
    Sec-->>API: Patron Verified (Patron ID: 12)
    API->>Agent: process_chat_inquiry(db, user, message, history)
    
    Agent->>Agent: Intent Classification & Coreference Resolution
    Note over Agent: Detects query references (e.g. "my loans", "where is seat S12")
    
    alt Needs Internal Database Facts
        Agent->>Tool: tool_get_patron_loans(patron_id=12)
        Tool->>DB: Query Active Loans & Due Dates
        DB-->>Tool: Return Loan Records
        Tool-->>Agent: Injected Loan Context Facts
    else Needs Spatial Wayfinding
        Agent->>Tool: tool_get_spatial_resource(seat_id=12)
        Tool->>DB: Query Coordinates & Directional Guidance
        DB-->>Tool: Floor 2, North Wing (X: 124.5, Y: 88.0)
        Tool-->>Agent: Injected Spatial Context Facts
    else Needs Catalog Monograph Recommendations
        Agent->>Tool: tool_search_catalogue(query="Distributed Systems")
        Tool->>DB: Hybrid Dense/Lexical Retrieval
        DB-->>Tool: Top 3 Matches + Availability
        Tool-->>Agent: Injected Catalog Context Facts
    end

    Agent->>Agent: Assemble Grounded Prompt with Citations Context
    Agent->>LLM: Dispatch Prompt with Grounding Constraints
    
    alt Provider Active (Gemini / OpenAI / Ollama)
        LLM-->>Agent: Raw Generated Response Text
    else Provider Unreachable or Unconfigured
        Agent->>Agent: Fallback to Deterministic Factual Synthesizer
        Note over Agent: Formats facts into structured deterministic reply
    end

    Agent->>Agent: Extract Structured Citations & Action Deep-Links
    Agent-->>API: EnhancedCopilotResponse (reply, tool_calls, citations)
    API-->>Patron: 200 OK Response with Visual Citations & Actions
```

---

## 7. Hybrid Search & Reciprocal Rank Fusion (RRF) Pipeline

The catalog search engine unifies dense vector semantics with exact lexical matching using Reciprocal Rank Fusion ($k = 60.0$):

```mermaid
flowchart TD
    Query["Patron Search Query\ne.g., 'deep learning fundamentals'"]
    
    subgraph Preprocess ["Preprocessing & Sanitization"]
        Sanitize["Input Sanitization\n(strip, max 500 chars)"]
        ISBNCheck{"Exact ISBN\nPattern?"}
    end

    subgraph Channel1 ["Channel 1: Lexical Search (SQL LIKE / Full-Text)"]
        SQLSearch["SQL Lexical Query\nTitle, Author, Subject, ISBN"]
        LexScore["Rank by Exact/Prefix/Keyword Matches"]
        LexTop["Lexical Top Candidates\n(Candidate Limit = 50)"]
    end

    subgraph Channel2 ["Channel 2: Dense Semantic Search (Vector Embedding)"]
        Embed["SentenceTransformer\nall-MiniLM-L6-v2 (384-dim)"]
        VectorDB["Cosine Similarity Scan against\nSerialized Book Embeddings"]
        SemTop["Semantic Top Candidates\n(min_score >= threshold)"]
    end

    subgraph Fusion ["Fusion & Re-Ranking Engine"]
        Union["Candidate Set Union\n(all_books_dict[id])"]
        RRF["Compute Reciprocal Rank Fusion\nRRF_Score = 1/(60 + Rank_Lex) + 1/(60 + Rank_Sem)"]
        TieBreak["Tie-Breaking:\n1. Exact ISBN Match (+100.0)\n2. Exact Title Match (+10.0)\n3. RRF Score\n4. ID ASC"]
    end

    subgraph Output ["Paged Results"]
        Paginate["Apply Pagination\n(page, page_size)"]
        Return["HybridSearchResponse\n(items, total, scores, ranks)"]
    end

    Query --> Sanitize --> ISBNCheck
    ISBNCheck -- "Parallel Dispatch" --> SQLSearch
    ISBNCheck -- "Parallel Dispatch" --> Embed
    SQLSearch --> LexScore --> LexTop --> Union
    Embed --> VectorDB --> SemTop --> Union
    Union --> RRF --> TieBreak --> Paginate --> Return
```

---

## 8. Grounded RAG Pipeline

```mermaid
flowchart LR
    PatronMsg["Patron Inquiry"] --> IntentGuard["Intent & Injection Guard"]
    IntentGuard --> RetrievalEngine["Context Retrieval Engine"]
    
    subgraph KnowledgeRetrieval ["Multi-Channel Knowledge Retrieval"]
        PolicyKB["Policy Markdown KB\n(Borrowing Limits, Grace Periods)"]
        LiveCatalog["Catalogue Holdings\n(Realtime Physical Availability)"]
        PatronProfile["Authenticated Profile\n(Active Loans, Fines, Holds)"]
        SpatialGraph["Spatial Coordinate Map\n(Floor Plans, Zones, Waypoints)"]
    end

    RetrievalEngine --> PolicyKB
    RetrievalEngine --> LiveCatalog
    RetrievalEngine --> PatronProfile
    RetrievalEngine --> SpatialGraph

    PolicyKB --> ContextAssembler["Context Boundary Assembler"]
    LiveCatalog --> ContextAssembler
    PatronProfile --> ContextAssembler
    SpatialGraph --> ContextAssembler

    ContextAssembler --> PromptBuilder["Grounded Prompt Synthesizer\n(Anti-Hallucination Strict Bounds)"]
    PromptBuilder --> ProviderAdapter["LLM Provider Adapter"]
    ProviderAdapter --> Verification["Response Citation Verification"]
    Verification --> ClientPayload["Verified Reply + Citations"]
```

---

## 9. Authentication & Password Recovery Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Patron as Patron
    participant Browser as Web Browser
    participant AuthRouter as /api/v1/auth
    participant PwdService as Password Reset Service
    participant SMTP as SMTP Mail Relay
    participant DB as Database

    Patron->>Browser: Enters Email on Forgot Password Page
    Browser->>AuthRouter: POST /auth/forgot-password {email}
    AuthRouter->>DB: Lookup User by Normalized Email
    alt User Found
        AuthRouter->>PwdService: generate_password_reset_token(user_id)
        PwdService->>PwdService: Generate 32-byte Cryptographic Token (secrets.token_urlsafe)
        PwdService->>PwdService: Compute SHA-256 Digest of Token
        PwdService->>DB: Store Token Record (hash, user_id, expires_at: now + 30m)
        PwdService->>SMTP: Dispatch Transactional HTML/Plain Reset Email
        Note over SMTP: Email contains single-use link: /reset-password?token=RAW_TOKEN
    else User Not Found
        Note over AuthRouter: Timing-safe uniform response to prevent user enumeration
    end
    AuthRouter-->>Browser: 200 OK (Generic instruction message)

    Patron->>Browser: Clicks Reset Link in Email
    Browser->>AuthRouter: POST /auth/reset-password {token, new_password}
    AuthRouter->>DB: Lookup Token Record by SHA-256(token)
    alt Token Valid, Unused, and Not Expired
        AuthRouter->>DB: Update User.password_hash (bcrypt 12-round)
        AuthRouter->>DB: Invalidate All User Reset Tokens (used=True)
        AuthRouter-->>Browser: 200 OK (Password successfully updated)
    else Invalid or Expired Token
        AuthRouter-->>Browser: 400 Bad Request (Invalid or expired token)
    end
```

---

## 10. Circulation & Hold Queue Allocation Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Patron as Patron
    actor Staff as Circulation Desk Staff
    participant Circ as Circulation Router
    participant HoldService as Hold Queue Engine
    participant DB as Relational Database

    Patron->>Circ: Request Loan on Title (All Copies Checked Out)
    Circ-->>Patron: 409 Conflict: No available physical copies
    Patron->>HoldService: POST /holds {book_id}
    HoldService->>DB: Check Active Hold Count & Existing Loans
    HoldService->>DB: Enqueue Hold (status: pending, queue_position: N+1)
    HoldService-->>Patron: 201 Created (Queued at position N+1)

    Note over Staff, DB: Later: Another patron returns a borrowed copy
    Staff->>Circ: POST /loans/{loan_id}/return
    Circ->>DB: Mark Loan as Returned (returned_at = now)
    Circ->>HoldService: on_book_copy_returned(book_copy_id)
    HoldService->>DB: Query Oldest Pending Hold for Book (FIFO)
    
    alt Pending Hold Exists
        HoldService->>DB: Allocate Copy to Hold
        HoldService->>DB: Update Hold: status = 'ready_for_pickup', pickup_expiry = now + 48h
        HoldService->>DB: Update BookCopy: status = 'reserved'
        HoldService->>DB: Insert Notification for Hold Patron
    else No Pending Holds
        HoldService->>DB: Update BookCopy: status = 'available'
    end
```

---

## 11. Cryptographic QR Collection Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Patron as Student Patron
    actor Staff as Desk Librarian
    participant Mobile as Student Mobile UI
    participant Scanner as Librarian Desk Scanner
    participant QRService as QR Collection Engine
    participant DB as Relational Database

    Patron->>Mobile: Navigates to Approved Hold / Loan
    Mobile->>QRService: POST /circulation/qr-collection/generate {hold_id}
    QRService->>QRService: Generate 32-byte secure token + 15m expiration
    QRService->>DB: Store BookCollectionToken (token, user_id, book_id, expires_at)
    QRService-->>Mobile: Return SVG/Canvas QR Payload
    Mobile->>Mobile: Render QR Code on Screen

    Patron->>Staff: Presents Screen at Library Collection Counter
    Staff->>Scanner: Scans QR Code
    Scanner->>QRService: POST /circulation/qr-collection/verify {token, copy_barcode}
    QRService->>DB: Verify Token (exists, unused, not expired, matches user)
    QRService->>DB: Verify Barcode matches Book and is Reserved for Hold
    QRService->>DB: Mark Token as Used (consumed_at = now)
    QRService->>DB: Complete Hold (status: fulfilled)
    QRService->>DB: Create Active Loan (patron_id, copy_id, due_date: now + 14d)
    QRService-->>Scanner: 200 OK (Checkout Confirmed: Loan ID created)
```

---

## 12. Course Reserves Management Workflow

```mermaid
flowchart TD
    Instructor["Faculty Instructor"] --> CreateCourse["Create Course Record\ne.g., CS-401 'Distributed Systems'"]
    CreateCourse --> AddReading["Add Required Reading Monograph\n(book_id, required_flag=True)"]
    AddReading --> PutOnReserve["Trigger Reserve Status\n(max_hours=2 or 24h, semester)"]
    
    subgraph OperationalEnforcement ["Circulation Policy Engine"]
        PutOnReserve --> MarkCopies["Mark Target Book Copies\nas 'course_reserve'"]
        MarkCopies --> PolicyGuard["Enforce Short-Loan Limit\n(e.g., 2-Hour In-Library Use Only)"]
        PolicyGuard --> BlockRenewal["Block Standard Self-Service Renewals"]
    end

    subgraph StudentAccess ["Student Experience"]
        Student["Enrolled Student"] --> ViewPortal["View Course Reading List\nin Teacher/Student Portal"]
        ViewPortal --> CheckAvail["Inspect Realtime Reserve Copy Status\n(In-Use vs On Shelf)"]
        CheckAvail --> CounterCheckout["Checkout at Desk under\nCourse Reserve Rules"]
    end
```

---

## 13. Dijkstra Spatial Wayfinding Engine

```mermaid
flowchart TD
    Req["Wayfinding Request\n(target_resource: 'seat', id: 45)"]
    
    subgraph SpatialLookup ["Resource Georeferencing"]
        Mapping["SpatialResourceMapping Query"] --> Coords["Target Coords (X: 180.5, Y: 92.0)\nFloor ID: 2, Zone: Quiet Study"]
    end

    subgraph GraphBuilding ["Graph Adjacency Construction"]
        FetchNodes["Fetch WayfindingNodes for Floor 2"]
        FetchEdges["Fetch WayfindingEdges (bidirectional)"]
        BuildAdj["Build Adjacency Map\nWeight = Euclidean Distance (X, Y)"]
    end

    subgraph Algorithm ["Shortest-Path Traversal (Dijkstra)"]
        IdentifyStart["Identify Start Node\n(Entrance Node or User Selected)"]
        MinHeap["Priority Queue (heapq)\n(cost, current_node, path)"]
        Relax["Edge Relaxation\nif new_cost < dist[neighbor]: update"]
    end

    subgraph PathSynthesis ["Guidance Generation"]
        FormatSteps["Synthesize Turn-by-Turn WayfindingSteps\n(Direction, Distance, Landmark)"]
        ReturnRoute["WayfindingRouteResponse\n(total_distance, steps, svg_polyline)"]
    end

    Req --> SpatialLookup
    Coords --> GraphBuilding
    FetchNodes --> BuildAdj
    FetchEdges --> BuildAdj
    BuildAdj --> IdentifyStart --> MinHeap --> Relax --> FormatSteps --> ReturnRoute
```

---

## 14. Intelligence & Demand Forecasting Architecture

```mermaid
flowchart LR
    subgraph DataCollection ["Historical Circulation Data Warehouse"]
        Loans["Completed Loans (365 Days)"]
        Holds["Hold Queue History & Abandonments"]
        Turns["Inventory Turn Events"]
        ZeroBorrows["Zero-Borrow Monograph Audit"]
    end

    subgraph Aggregation ["Daily Metric Aggregator"]
        Bucket["Group by Date & Category"]
        Velocity["Calculate Daily Circulation Velocity"]
        Turnover["Compute Category Turnover Rate"]
    end

    subgraph Engine ["Forecasting & Recommendation Engine"]
        HW["Holt-Winters / EMA\nTime-Series Smoothing"]
        Trend["Trend & Seasonality Decomposition"]
        Acquisition["Acquisition Recommendation Scoring\nScore = (Hold_Pressure * 0.6) + (Velocity * 0.4)"]
    end

    subgraph ExecutiveUI ["Librarian Intelligence Centre UI"]
        KPICards["Executive KPI Cards\n(Active Loans, Turnover, At-Risk Titles)"]
        Chart["30-Day Demand Forecast Chart\nwith Historical Overlay"]
        RecomTable["Automated Acquisition Order Table\n(Recommended Copy Quantities)"]
    end

    Loans --> Bucket
    Holds --> Bucket
    Turns --> Velocity
    ZeroBorrows --> Turnover
    Bucket --> HW
    Velocity --> HW
    HW --> Trend
    Trend --> Acquisition
    Turnover --> Acquisition
    HW --> Chart
    Trend --> KPICards
    Acquisition --> RecomTable
```
