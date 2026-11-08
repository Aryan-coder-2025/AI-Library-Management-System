# Athenaeum: Changelog

All notable changes to the Athenaeum codebase are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — Stage 12.14 & Release Engineering (2026-11-08)

### Added
- **Authentication & Self-Registration (Stage 12.9)**:
  - Added public student registration endpoint (`/api/v1/auth/register`) with automatic role assignment and profile generation.
  - Implemented dual-identifier authentication supporting login via either verified email or unique username.
  - Added 12-character baseline password policy with complexity validation.
  - Added frontend registration (`Register.tsx`) and enhanced sign-in view (`SignIn.tsx`).
- **Email Infrastructure & Password Recovery (Stage 12.10)**:
  - Built reusable transactional SMTP email service (`email.py`) with TLS support and HTML/text templates.
  - Implemented secure password recovery (`/api/v1/auth/forgot-password` and `/api/v1/auth/reset-password`) using single-use SHA-256 hashed 32-byte tokens.
  - Created frontend password recovery workflows (`ForgotPassword.tsx` and `ResetPassword.tsx`).
- **Academic Research Discovery & Holds (Stage 12.11)**:
  - Integrated external academic discovery aggregator (`services/research/`) combining OpenAlex, arXiv, and Crossref APIs with deduplication and rate-limiting.
  - Implemented priority book waitlist and hold queue system (`services/holds.py`) with pickup expiration and auto-allocation on copy return.
  - Added interactive scholarly discovery UI (`AcademicResearchDiscovery.tsx`).
- **Canonical Feature Completion (Stage 12.14)**:
  - Implemented cryptographic QR book collection system (`services/qr_collection.py`, `QRCollectionModal.tsx`).
  - Implemented Course Reserves policy enforcement (`services/courses.py`, `CIRC-06`).
  - Added Teacher Portal with course reading lists and syllabus upload (`TeacherPortal.tsx`, `PORT-03`).
  - Implemented lost and damaged copy processing workflow (`services/inventory_ops.py`, `CopyStatusModal.tsx`, `CIRC-07`).
  - Built Librarian Intelligence Centre with executive KPIs, Holt-Winters demand forecasting, inventory analytics, and automated acquisition workflows (`services/intelligence.py`, `LibrarianIntelligenceCenter.tsx`, `INTEL-01` to `INTEL-06`).
- **AI Provider & Gemini Configuration Resolution**:
  - Unified `LLM_API_KEY`, `GEMINI_API_KEY`, and `GOOGLE_API_KEY` resolution in `config.py`.
  - Pinned default model to `gemini-3.1-flash-lite-preview`.
  - Added multi-fallback key resolution in `copilot.py` and `ai_comparison.py`.
  - Pinned automated test suites to `LLM_PROVIDER=fallback` in `conftest.py` for reproducible offline testing.

### Verified
- Full backend test suite passing: 393 passed, 2 skipped across 26 test suites (395 total).
- Frontend production build passing: 147 modules transformed, 0 errors.
- 4 protected canonical database hashes verified identical (zero corruption).

---

## [10.6.0] — Stage 10 Feature Release (2026-11-06)

### Added
- Multi-floor interactive SVG spatial layout editor and wayfinding engine (`services/spatial.py`).
- Dijkstra shortest-path navigation algorithm for seat and room directions.
- Real-time occupancy telemetry tracking with anti-collision seat reservations.
- Hierarchical knowledge graph explorer (`Subject` $\rightarrow$ `Topic` $\rightarrow$ `Concept`).
- Multi-model comparison studio auditing response latency, token usage, and factual grounding overlap.
- Agentic Librarian Copilot with bounded conversational history and tool-calling capabilities.

---

## [2.0.0] — Core Foundation & Hardened Auth (Stage 2)

### Added
- Initial FastAPI application bootstrap with modular domain routers.
- RBAC authorization model (Guest, Student, Teacher, Librarian, Administrator).
- Bcrypt password hashing and HttpOnly JWT cookie session management.
- Baseline monograph and physical copy circulation data models.

