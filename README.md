# AI-Powered Smart Library Management System

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.3-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4-646CFF.svg)](https://vitejs.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-337%20Passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/Academic-Project-informational.svg)]()

A comprehensive, production-grade enterprise library automation platform designed for modern academic institutions. The system integrates full circulation lifecycles, hybrid lexical and dense semantic discovery, physical study-space booking with interactive SVG floor plans and wayfinding, real-time occupancy telemetry, and a multi-pillar AI intelligence layer comprising hierarchical knowledge graphs, multi-model comparison studios, and an agentic librarian copilot with verifiable RAG recommendations.

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. User Roles & Access Control](#2-user-roles--access-control)
- [3. Five AI Pillars](#3-five-ai-pillars)
- [4. Core Features & Capabilities](#4-core-features--capabilities)
- [5. System Architecture](#5-system-architecture)
- [6. Technology Stack](#6-technology-stack)
- [7. Installation & Setup Guide](#7-installation--setup-guide)
- [8. AI Provider Configuration & Simulation Mode](#8-ai-provider-configuration--simulation-mode)
- [9. Testing & Quality Assurance](#9-testing--quality-assurance)
- [10. Canonical Feature Scope & Implementation Status](#10-canonical-feature-scope--implementation-status)
- [11. Synthetic Data & Simulation Disclosures](#11-synthetic-data--simulation-disclosures)
- [12. Project Documentation Links](#12-project-documentation-links)

---

## 1. Project Overview

Academic libraries face a dual challenge: managing traditional physical resources (monograph inventory, multi-level study desks, group collaboration rooms) while meeting patron expectations for modern, AI-augmented digital discovery. 

The **AI-Powered Smart Library Management System** resolves these challenges by providing:
- **Unified Operations:** End-to-end management of monographs, physical copy barcodes, circulation loans, patron quotas, and overdue fines.
- **Physical & Spatial Discovery:** Interactive multi-floor SVG maps, real-time desk/room booking with anti-collision triggers, turn-by-turn wayfinding, and QR-verified check-ins.
- **Transparent AI Integration:** Moving beyond opaque chatbots to provide structured tool calling, deterministic local fallbacks, verifiable structured citations, and side-by-side model auditing.

---

## 2. User Roles & Access Control

The platform enforces strict Role-Based Access Control (RBAC) via cryptographically signed `HttpOnly` JWT cookies:

| Role | Access Privileges | Primary Interface |
| :--- | :--- | :--- |
| **Public Guest (OPAC)** | Unauthenticated public catalog search and monograph availability. Individual copy barcodes and patron identities are strictly hidden. | Public OPAC View |
| **Student Patron** | Search catalog (lexical, semantic, hybrid), request loans, self-service loan renewals (14 days), reserve study seats/rooms, view QR passes, access AI Copilot. | Student Portal |
| **Teacher / Faculty** | Extended borrowing quotas (10 items), extended loan durations (30 days), priority study room reservations, academic syllabus support. | Teacher / Faculty View |
| **Librarian Staff** | Full circulation desk (checkout, return, override renewals), physical copy inventory management, floor plan layout editor, occupancy telemetry oversight. | Librarian Circulation Desk |
| **Administrator** | System configuration, database seeding, AI model comparison studio, spatial layout publishing, and role provisioning. | Admin / Staff Management |

---

## 3. Five AI Pillars

The platform implements the five original architectural AI requirements as functional, interconnected subsystems:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FIVE AI CORE PILLARS                            │
├───────────────────────────────┬────────────────────────────────────────┤
│ 1. Knowledge Representation   │ Hierarchical Subject-Topic-Concept     │
│                               │ DAG with monograph linkage             │
├───────────────────────────────┼────────────────────────────────────────┤
│ 2. Search-Based Navigation    │ Contextual academic pathways and       │
│                               │ concept relationship exploration       │
├───────────────────────────────┼────────────────────────────────────────┤
│ 3. Intelligent Librarian Agent│ Tool-calling agent: spatial guidance,  │
│                               │ live occupancy, loans, policy lookup   │
├───────────────────────────────┼────────────────────────────────────────┤
│ 4. Modern AI Model Comparison │ Side-by-side evaluation: latency,      │
│                               │ tokens, factual grounding auditing     │
├───────────────────────────────┼────────────────────────────────────────┤
│ 5. Grounded RAG Assistant     │ Factual monograph recommendations with │
│                               │ verifiable structured citations        │
└───────────────────────────────┴────────────────────────────────────────┘
```

1. **Pillar 1: Knowledge Representation (`Subject` $\rightarrow$ `Topic` $\rightarrow$ `Concept`)**
   - Implements a relational knowledge hierarchy backed by database models (`subjects`, `topics`, `concepts`, and `concept_book_associations`).
   - Links academic monographs to discrete conceptual entities, enabling patrons to explore foundational and specialized topics in computer science, machine learning, physics, mathematics, and cybersecurity.
2. **Pillar 2: Search-Based Conceptual Navigation**
   - Interactive conceptual search (`/api/knowledge/search?q=...`) resolving queries against subjects, topics, and concepts.
   - Provides explainable academic context paths (e.g., `Computer Science > Artificial Intelligence & Machine Learning > Neural Networks`).
3. **Pillar 3: Intelligent Librarian Agent**
   - Genuine tool-calling Copilot with multi-turn bounded context (6 historical messages) and coreference resolution.
   - Dispatches deterministic tools: `tool_get_spatial_resource` for physical locations, `tool_get_available_spaces` for live room/seat occupancy, `tool_get_patron_loans` for circulation records, and `tool_search_catalogue` for holdings.
   - Prevents cross-patron information leakage by binding patron loan queries strictly to the authenticated session user.
4. **Pillar 4: Modern AI Comparison Studio**
   - Side-by-side prompt execution across configured providers (Google Gemini, OpenAI GPT-4o, and Local Deterministic rule planner).
   - Computes empirical metrics: response latency in milliseconds, token counts (prompt, completion, total), and mathematical factual grounding overlap against library policy metadata.
   - Features transparent status badges distinguishing live remote execution from standardized local simulation benchmarks.
5. **Pillar 5: Grounded RAG Recommendation Assistant**
   - Hybrid retrieval-augmented generation combining dense vector embeddings with lexical catalog metadata.
   - Returns structured citations (`StructuredCitation`) with verifiable source types (`monograph`, `policy`, `study_space`) and direct action links.

---

## 4. Core Features & Capabilities

- **Hybrid Lexical & Semantic Search (RRF $k=60$):** Fuses BM25-style lexical matching with 384-dimensional dense embeddings (`all-MiniLM-L6-v2`), featuring exact ISBN-10/13 normalization, checksum validation, and title pinning.
- **Physical Study-Space Subsystem:** 150 individual study seats (power/monitor amenities) and 10 group study rooms across 4 floor zones. Relational database triggers and serialization locks block double-booking.
- **Interactive Multi-Floor SVG Floor Plans:** 4 levels (Ground Floor, 1st Floor Commons, 2nd Floor Silent Loft, 3rd Floor Research Stacks) with normalized coordinate projection and Dijkstra shortest-path wayfinding.
- **QR Check-In & Automated Sweeper:** Time-windowed check-in (15-min grace period) with HMAC-SHA256 signed QR passes. Automated idempotent background sweeper cancels no-shows and frees quotas.
- **Occupancy Tracking & Diurnal Analytics:** Real-time occupancy aggregation by zone and room, historical daily trends, and 24-hour peak-hour heatmaps with synthetic provenance tagging.
- **Patron Self-Service:** Password updates with bcrypt hashing, active loan monitoring, one-click 14-day renewal, and in-app overdue notification alerts.

---

## 5. System Architecture

The application adopts a clean, layered architecture enforcing modularity and separation of concerns:

```
┌────────────────────────────────────────────────────────┐
│                   React 19 Frontend                    │
│   (TypeScript, Vite, SVG Floor Plans, Copilot Drawer)  │
└───────────────────────────┬────────────────────────────┘
                            │ REST / JSON (JWT Cookies)
┌───────────────────────────▼────────────────────────────┐
│                  FastAPI Backend Core                  │
│  ├── API Routers (/api/auth, /books, /spaces, /copilot) │
│  ├── Security Middleware (CSRF, CORS, Rate Limiting)   │
│  └── Service Layer (Spatial, Semantic, AI Comparison)  │
└───────────────────────────┬────────────────────────────┘
                            │ SQLAlchemy 2.0 (ORM / Core)
┌───────────────────────────▼────────────────────────────┐
│                 SQLite Relational Database             │
│  ├── WAL Mode & Foreign Key Integrity Constraints      │
│  ├── Triggers (Anti-collision, Role Overlap Guards)    │
│  └── Alembic Version Migrations (Head: a1b2c3d4e5f6)   │
└────────────────────────────────────────────────────────┘
```

---

## 6. Technology Stack

- **Backend Framework:** FastAPI 0.110+ (ASGI runtime via Uvicorn)
- **Database & ORM:** SQLite 3 (WAL mode enabled) via SQLAlchemy 2.0+
- **Schema Migrations:** Alembic 1.13+
- **Data Validation & Schemas:** Pydantic v2 (Strict field validators)
- **Security & Authentication:** `passlib[bcrypt]`, `python-jose` (HS256 JWT cookies)
- **Mathematical & Vector Processing:** `numpy` 1.26+, cosine similarity ranking
- **Frontend Framework:** React 19.3+, TypeScript, Vite 5.4+
- **Testing Infrastructure:** `pytest` 8.4+, `pytest-asyncio`, `httpx`, `TestClient`

---

## 7. Installation & Setup Guide

### 7.1 Prerequisites
- **Python 3.11.x** (Verify with `python --version`)
- **Node.js v20+** or **v22+** (Verify with `node --version`)
- **PowerShell 7 (pwsh)** or standard Windows PowerShell / Linux bash
- **Git** (Verify with `git --version`)

### 7.2 Repository Setup

```bash
git clone https://github.com/Aryan-coder-2025/AI-Library-Management-System.git
cd AI-Library-Management-System
```

### 7.3 Backend Setup

1. **Create and Activate Virtual Environment:**
   ```powershell
   # Windows PowerShell
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies:**
   ```powershell
   python -m pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy the provided template:
   ```powershell
   Copy-Item .env.example .env     # Windows
   cp .env.example .env            # Linux/macOS
   ```
   *(By default, `.env` is preconfigured for development. SQLite automatically resolves to `backend/library.db` if `DATABASE_URL` is omitted).*

4. **Initialize Database & Apply Migrations:**
   ```powershell
   cd backend
   python -m alembic upgrade head
   ```

5. **Seed Demonstration Data (Idempotent):**
   ```powershell
   python -m app.seed_demo
   cd ..
   ```
   *Seeds academic monographs, copy barcodes, demonstration user accounts, study zones, seats, rooms, and precomputed embeddings.*

### 7.4 Frontend Setup

1. **Install Node Dependencies:**
   ```powershell
   cd frontend
   npm install
   ```

2. **Verify Production Build:**
   ```powershell
   npm run build
   ```

### 7.5 Running the Development Services

1. **Start the Backend Server (Port 8000):**
   ```powershell
   cd backend
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   Interactive Swagger documentation will be available at: `http://127.0.0.1:8000/docs`

2. **Start the Frontend Application (Port 5173):**
   ```powershell
   cd frontend
   npm run dev
   ```
   Access the web interface at: `http://localhost:5173`

---

## 8. AI Provider Configuration & Simulation Mode

The system features an autonomous fallback engine:
- **No External API Keys Required:** If `LLM_API_KEY` is omitted or left blank in `.env`, the system automatically activates its **Deterministic Local Planner**. In this mode, the Librarian Agent and Copilot run using validated rule-based heuristics and live database facts.
- **Model Comparison Studio in Simulation Mode:** In the Model Comparison Studio, if external API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`) are not provided, external models run under standardized local simulation benchmarks. Latency, token usage, and grounding metrics are clearly tagged with yellow `🟡 Simulated Fallback` badges, preventing simulated performance from being mistaken for live provider telemetry.
- **Configuring Live Remote Providers (Optional):**
  To enable live remote completions, configure `.env`:
  ```ini
  LLM_PROVIDER="gemini"                   # or "openai", "auto"
  LLM_API_KEY="your-actual-api-key"
  LLM_MODEL_NAME="gemini-1.5-flash"
  ```

---

## 9. Testing & Quality Assurance

The codebase includes an extensive automated test suite with **337 passing tests and 0 failures**:

```powershell
# Run the complete test suite from repository root
.\venv\Scripts\python.exe -m pytest backend/tests -v

# Run targeted AI Knowledge & Copilot tests
.\venv\Scripts\python.exe -m pytest backend/tests/test_knowledge_ai.py -v

# Run spatial floor plans & wayfinding tests
.\venv\Scripts\python.exe -m pytest backend/tests/test_spatial.py -v

# Run frontend production build check
npm run build --prefix frontend
```

---

## 10. Canonical Feature Scope & Implementation Status

The project strictly preserves the canonical 34-feature scope across 6 functional domains:

| Status Classification | Count | Description |
| :--- | :---: | :--- |
| **`COMPLETE AND VERIFIED`** | **19** | Fully functional and regression-verified across backend, frontend, and tests (`PORT-01`, `PORT-02`, `PORT-04`, `PORT-05`, `PORT-06`, `DISC-01`, `DISC-02`, `DISC-03`, `DISC-04`, `CIRC-01`, `CIRC-04`, `CIRC-05`, `SPAC-01`, `SPAC-02`, `SPAC-03`, `SPAC-04`, `SPAC-05`, `ADV-01`, `ADV-03`). |
| **`COMPLETE WITH LIMITATIONS`** | **1** | Fully functional subject to documented candidate-pool bounds (`DISC-05` Hybrid Search $\le 200$ items). |
| **`PARTIALLY IMPLEMENTED`** | **3** | Core backend schemas and services active; secondary workflows deferred (`PORT-03`, `CIRC-02`, `CIRC-07`). |
| **`IMPLEMENTED BUT NOT VERIFIED`**| **1** | External live LLM adapter code complete, awaiting live remote key configuration (`ADV-02`). |
| **`NOT IMPLEMENTED`** | **8** | Enterprise institutional planning modules scheduled for subsequent phases (`CIRC-03`, `CIRC-06`, `INTEL-01` to `INTEL-06`). |
| **`REQUIRES SEPARATE APPROVAL`** | **2** | Restricted features subject to explicit ethical or financial approval (`ADV-04` Biometrics, `ADV-05` Electronic Payments). |
| **Total Canonical Features** | **34** | **100% of canonical feature IDs accounted for without scope reduction.** |

For exhaustive per-feature acceptance criteria, line references, and architectural limitations, see [`docs/implementation-status.md`](docs/implementation-status.md).

---

## 11. Synthetic Data & Simulation Disclosures

- **Synthetic Circulation & Patron Records:** All demonstration patron names, email addresses, active loans, and circulation histories generated by `app.seed_demo` are synthetic mock data generated for testing.
- **Synthetic Bibliographic Data:** Monograph titles and ISBNs reflect educational reference texts; operational statuses and barcode identifiers are simulated for testing.
- **Simulation Benchmarks:** In the AI Model Comparison Studio, benchmark latencies and token usage for unconfigured external providers are deterministic fixtures clearly labeled as `Simulated Fallback`.

---

## 12. Project Documentation Links

- [System Architecture Specification](docs/architecture.md)
- [Development Environment & Setup Guide](docs/development-setup.md)
- [Demonstration & Evaluator Walkthrough Guide](docs/demo-guide.md)
- [Spatial Floor Plans & Wayfinding Architecture](docs/spatial-floor-plans-architecture.md)
- [Canonical 34-Feature Implementation Status](docs/implementation-status.md)
- [API Endpoints Reference](docs/api-reference.md)
- [Database Schema & Integrity Controls](docs/database-schema.md)

---

## 13. Academic Notice

This project was developed as an educational and technical demonstration of modern full-stack engineering, database integrity, and verifiable artificial intelligence integration in library informatics.

