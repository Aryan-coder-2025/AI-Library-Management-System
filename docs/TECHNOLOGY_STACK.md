# Athenaeum: Technology Stack Specification

## 1. Overview & Architectural Philosophy

**Athenaeum** is built on a modern, decoupled web architecture engineered for academic rigor, operational safety, transparent AI integration, and developer velocity. Every dependency in the system was selected according to three core criteria:
1. **Predictability & Type Safety**: End-to-end static typing across Python (Pydantic v2 / MyPy conventions) and TypeScript (Strict Mode).
2. **Deterministic Fallbacks**: AI capabilities fail gracefully to verifiable rule-based and local database logic when remote cloud services are unreachable or unconfigured.
3. **Storage & Schema Integrity**: Strict relational modeling with foreign keys, checks, and transactional rollback semantics rather than schema-less stores.

---

## 2. Technology Inventory Matrix

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

## 3. Backend Technologies & Design Rationale

### 3.1 FastAPI & Pydantic v2
FastAPI was chosen for its native asynchronous capabilities, automatic generation of OpenAPI/Swagger interactive documentation, and high execution speed built on Starlette. Combined with Pydantic v2, all request bodies, query parameters, and response bodies undergo compile-time and runtime validation.

- **Location**: `backend/app/main.py`, `backend/app/routers/`
- **Design Decision**: Pydantic schemas are segregated from SQLAlchemy persistence models in `backend/app/schemas.py`. This ensures sensitive internal state (such as bcrypt password hashes, internal database IDs, or admin flags) is never accidentally exposed in API serialization layers.

### 3.2 SQLAlchemy 2.0 & Alembic
The persistence layer uses the modern SQLAlchemy 2.0 declarative syntax (`Mapped[...]` and `mapped_column(...)`), which guarantees type consistency with Python type checkers and avoids runtime model reflection.

- **Location**: `backend/app/models.py`, `backend/app/database.py`, `backend/alembic/`
- **Design Decision**: The database engine is configured with `PRAGMA foreign_keys = ON` for SQLite, guaranteeing relational integrity at the storage engine level. Write sessions use an explicit atomic transaction context manager (`atomic_write`) to guarantee all-or-nothing rollback on runtime exceptions.

### 3.3 Passlib, Python-Jose & Dedicated Key Derivation
Security relies on industry-standard cryptographic libraries:
- **Location**: `backend/app/auth.py`, `backend/app/config.py`
- **Design Decision**: In addition to the primary `JWT_SECRET_KEY`, Athenaeum enforces a distinct `SPACES_QR_SECRET_KEY` for study-space QR token generation. If the two keys are identical, configuration validation raises a runtime error, preventing lateral credential reuse attacks.

---

## 4. Artificial Intelligence & Vector Processing Stack

### 4.1 SentenceTransformers (`all-MiniLM-L6-v2`)
Dense semantic discovery relies on the local sentence-transformers library.
- **Model**: `all-MiniLM-L6-v2`
- **Embedding Dimensions**: 384 floating-point numbers.
- **Location**: `backend/app/services/embedding.py`, `backend/app/services/semantic.py`
- **Design Decision**: Rather than requiring an external vector database (e.g., Pinecone, Milvus, Qdrant) that would introduce external operational complexity and cost, embeddings are stored directly in the relational database as binary BLOBs using `numpy.ndarray.tobytes()`. At query time, candidate vectors are deserialized and compared via vectorized NumPy dot products, delivering sub-15ms cosine similarity across typical university catalog sizes.

### 4.2 Multi-Provider LLM Abstraction
The AI Assistant operates over a provider-agnostic interface:
- **Location**: `backend/app/services/copilot.py`, `backend/app/services/ai_comparison.py`
- **Supported Providers**:
  - **Google Gemini**: Remote cloud generation using `gemini-3.1-flash-lite-preview` via Google AI Studio API keys (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, or `LLM_API_KEY`).
  - **OpenAI**: Remote cloud generation using GPT-4o (`OPENAI_API_KEY`).
  - **Ollama**: Local workstation inference on `http://localhost:11434/v1` for offline privacy-first deployments.
  - **Deterministic Rule Engine**: Standardized local synthesizer that uses live database queries, library policy markdown, and algorithmic fact assembly to answer queries when no API key is available.

---

## 5. Frontend Technologies & Design Rationale

### 5.1 React 19 & Vite 5.4
The client interface is built with React 19, taking advantage of modern functional components, standard hooks (`useState`, `useEffect`, `useCallback`, `useMemo`), and zero runtime CSS overhead.
- **Location**: `frontend/src/`
- **Design Decision**: Vite was selected over legacy Webpack / Create React App due to its instant cold server starts via native ES modules, blazing-fast HMR (Hot Module Replacement), and highly optimized production Rollup builds (147 modules compiled in under 1.3 seconds).

### 5.2 Atomic CSS & Glassmorphism Design System
Rather than importing heavy third-party UI component libraries (e.g., Material UI, Ant Design) that inflate bundle sizes and enforce generic aesthetics, Athenaeum uses a custom glassmorphism design system in `frontend/src/index.css`.
- **Location**: `frontend/src/index.css`, `frontend/src/services/theme.ts`
- **Features**: CSS custom properties for dynamic light/dark theming, backdrop blur filters (`backdrop-filter: blur(16px)`), accessible high-contrast typography, and responsive grid layouts.

---

## 6. External Academic Integration Stack

To provide patrons with external scholarly discovery beyond physical library holdings, Athenaeum integrates three open academic APIs via asynchronous HTTPX clients:
1. **OpenAlex**: Global open scholarly graph API providing normalized bibliographic metadata, topic taxonomy, and open-access URLs.
2. **arXiv Export API**: Pre-print repository querying physics, mathematics, and computer science e-prints with XML feed normalization.
3. **Crossref Metadata API**: Digital Object Identifier (DOI) registration agency providing peer-reviewed publication metadata.

All external calls are governed by strict timeouts (5.0s), resilient rate-limiting, and an internal deduplication aggregator that merges identical DOIs across providers.

