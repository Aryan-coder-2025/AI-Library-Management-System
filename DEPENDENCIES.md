# Athenaeum: Dependency Inventory Specification

This document provides a verified, comprehensive inventory of all software dependencies utilized across Athenaeum's backend and frontend tiers. Every package version listed is derived directly from the project's dependency manifests (`requirements.txt`, `package.json`, and lockfiles) and confirmed against active virtual environments.

---

## 1. Backend Runtime Dependencies

These libraries are required for the execution of the Athenaeum FastAPI application and background worker threads.

| Package | Manifest Constraint | Verified Installed Version | Purpose in Athenaeum | Primary Source File(s) |
|---|---|---|---|---|
| **fastapi** | `>=0.110.0,<1.0.0` | `0.162.0` | Core ASGI web framework providing routing, request handling, OpenAPI generation. | `backend/app/main.py`, `backend/app/routers/*` |
| **uvicorn[standard]** | `>=0.28.0,<1.0.0` | `0.54.0` | Asynchronous ASGI server process worker and HTTP event loop. | `backend/app/main.py` |
| **sqlalchemy** | `>=2.0.28,<3.0.0` | `2.1.6` | Relational Object-Relational Mapping (ORM) and SQL expression engine. | `backend/app/models.py`, `backend/app/database.py` |
| **alembic** | `>=1.13.1,<2.0.0` | `1.20.1` | Relational database schema versioning, migration generation, and upgrades. | `backend/alembic/*`, `backend/alembic.ini` |
| **pydantic** | `>=2.6.4,<3.0.0` | `2.14.1` | Compile-time and runtime data validation, schema definitions, and serialization. | `backend/app/schemas.py` |
| **pydantic-settings** | `>=2.2.1,<3.0.0` | `2.16.1` | Multi-source environment variable discovery, `.env` file hierarchy resolution. | `backend/app/config.py` |
| **python-jose[cryptography]** | `>=3.3.0,<4.0.0` | `3.5.0` | JSON Web Token (JWT) encoding, signing, decoding, and cryptographic verification. | `backend/app/auth.py` |
| **passlib[bcrypt]** | `>=1.7.4,<2.0.0` | `1.7.4` | Password hashing using 12-round salted Bcrypt algorithm. | `backend/app/auth.py` |
| **python-multipart** | `>=0.0.9,<1.0.0` | `0.0.32` | Form-data parsing for file uploads (e.g., syllabus PDF uploads) and OAuth2 forms. | `backend/app/routers/auth.py`, `backend/app/routers/courses.py` |
| **httpx** | `>=0.27.0,<1.0.0` | `0.28.1` | Asynchronous HTTP client for external LLMs and academic research APIs. | `backend/app/services/research/*`, `copilot.py` |
| **numpy** | `>=1.26.0,<3.0.0` | `2.4.6` | Vector mathematical operations, cosine similarity matrix computation, binary serialization. | `backend/app/services/semantic.py`, `embedding.py` |
| **python-dotenv** | (transitive) | `1.2.4` | Lower-level `.env` file parsing engine used by configuration resolvers. | `backend/app/config.py` |

---

## 2. Machine Learning & Embedding Dependencies (Local Inference)

These libraries provide dense semantic search and local vector embedding capabilities.

| Package | Verified Installed Version | Purpose in Athenaeum | Hardware / Execution Profile |
|---|---|---|---|
| **sentence-transformers** | `6.2.0` | Encodes textual metadata into 384-dimensional dense semantic vectors using `all-MiniLM-L6-v2`. | CPU / CUDA acceleration where available. |
| **torch** | `2.14.1` | Deep learning runtime engine powering the transformer tensor computations. | CPU runtime on standard workstations. |
| **transformers** | `5.21.0` | Hugging Face model tokenizer, architecture definitions, and weight loaders. | Loads pre-trained transformer model weights. |
| **scikit-learn** | `1.9.1` | Auxiliary numerical algorithms, cosine distance metrics, and statistical routines. | Used in analytical clustering and metrics. |
| **scipy** | `1.17.1` | Scientific computation library supporting advanced mathematical routines. | Numerical analysis and time-series helpers. |

---

## 3. Backend Test & Quality Assurance Dependencies

These libraries are utilized during automated testing, security validation, and schema regression verification.

| Package | Manifest Constraint | Verified Installed Version | Purpose in Test Harness |
|---|---|---|---|
| **pytest** | `>=8.1.1,<9.0.0` | `8.4.2` | Primary test execution harness, assertion runner, and fixture manager. |
| **pytest-asyncio** | `>=0.23.6,<1.0.0` | `0.26.0` | Asynchronous coroutine fixture support for testing async FastAPI routes. |
| **iniconfig** | (transitive) | `2.3.1` | Configuration parser for `pytest.ini`. |
| **pluggy** | (transitive) | `1.7.0` | Pytest plugin orchestration framework. |

---

## 4. Frontend Runtime Dependencies

These packages are bundled into the client-side single page application.

| Package | Manifest Constraint | Installed Version | Purpose in Frontend |
|---|---|---|---|
| **react** | `^19.3.1` | `19.3.1` | Core UI component lifecycle, virtual DOM reconciliation, state hooks. |
| **react-dom** | `^19.3.1` | `19.3.1` | DOM-specific rendering methods for web browsers. |
| **qrcode** | `^1.5.4` | `1.5.4` | Generates 2D Quick Response (QR) matrices on HTML5 canvas elements for book collection. |
| **@rolldown/binding-wasm32-wasi** | `^1.2.15` | `1.2.15` | High-performance WASM compilation binding supporting Rollup optimizations. |

---

## 5. Frontend Development & Build Tooling

These packages are required to type-check, lint, and bundle the client-side application.

| Package | Manifest Constraint | Installed Version | Purpose |
|---|---|---|---|
| **vite** | `^5.4.11` | `5.4.11` | Next-generation frontend build tool and local development server. |
| **@vitejs/plugin-react** | `^4.3.3` | `4.3.3` | Babel/SWC-based Fast Refresh support for React in Vite. |
| **typescript** | `~6.0.3` | `5.8+` engine | Static type checker verifying component props, interfaces, and API types. |
| **oxlint** | `^1.88.0` | `1.88.0` | High-performance Rust-based JavaScript/TypeScript linter. |
| **@types/react** | `^19.3.0` | `19.3.0` | TypeScript type declarations for React core library. |
| **@types/react-dom** | `^19.3.0` | `19.3.0` | TypeScript type declarations for React DOM rendering methods. |
| **@types/qrcode** | `^1.5.6` | `1.5.6` | TypeScript type declarations for the `qrcode` library. |
| **@types/node** | `^24.19.2` | `24.19.2` | TypeScript type definitions for Node.js platform APIs (used in Vite configs). |

---

## 6. Optional External Providers & Services

The following external services are supported via standard HTTP protocols and require no proprietary client SDKs:

1. **Google Gemini API**: Accessed via raw REST endpoints (`https://generativelanguage.googleapis.com/v1beta/models/...`) with standard HTTPX client calls.
2. **OpenAI API**: Accessed via standard OpenAI-compatible completions endpoints (`/v1/chat/completions`).
3. **Ollama**: Accessed via local REST endpoint (`http://localhost:11434/v1`).
4. **OpenAlex / arXiv / Crossref**: Accessed via public HTTPS REST endpoints.
5. **SMTP Relay**: Accessed via standard Python `smtplib` and `ssl` modules over TLS (Port 587).

