# Athenaeum: Security Policy & Vulnerability Disclosure

## 1. Security Overview & Commitment

Athenaeum is designed to manage institutional library records, patron personal identifiable information (PII), physical facility access, and academic research workflows. We take security seriously and follow defense-in-depth principles across the entire application lifecycle.

This document describes the security controls enforced within Athenaeum, responsible disclosure guidelines, and known architectural threat boundaries.

---

## 2. Implemented Security Controls

### 2.1 Cryptographic Key Separation
Athenaeum strictly prohibits the reuse of cryptographic keys across different domains. The configuration loader (`backend/app/config.py`) validates that:
- `JWT_SECRET_KEY`: Used exclusively for signing authentication session tokens.
- `SPACES_QR_SECRET_KEY`: Dedicated key used exclusively for signing study-space QR access tokens.
- **Enforcement**: If `SPACES_QR_SECRET_KEY` equals `JWT_SECRET_KEY`, the application terminates at startup with a `ValueError`.

### 2.2 Password Storage & Lifecycle
- **Algorithm**: Passwords are hashed using Passlib's 12-round salted `bcrypt` implementation (`passlib[bcrypt]`).
- **Policy**: A minimum password length of 12 characters is strictly enforced at both Pydantic schema validation and frontend input layers.
- **Recovery**: Password recovery tokens are 32-byte cryptographically secure random values generated with Python's `secrets.token_urlsafe(32)`. Only their SHA-256 digests are stored in the database. Reset tokens expire after 30 minutes and are permanently invalidated upon use.

### 2.3 Session & Transport Security
- **HttpOnly Cookies**: Session tokens are issued inside `HttpOnly`, `SameSite=Lax` cookies, preventing client-side JavaScript access and mitigating cross-site scripting (XSS) session theft.
- **CORS Protection**: Cross-Origin Resource Sharing is locked down via FastAPI's `CORSMiddleware` using an explicit origin whitelist configured in `ALLOWED_ORIGINS`.

### 2.4 SQL Injection & Data Isolation
- **Parameterized Queries**: All database operations use SQLAlchemy 2.0 ORM expressions and parameterized queries. Raw string concatenation in SQL statements is strictly forbidden.
- **Foreign Key Constraints**: SQLite engines are explicitly booted with `PRAGMA foreign_keys = ON` to enforce database-level relational integrity and prevent orphaned records.
- **Patron Data Privacy**: The AI Copilot agent binds patron queries strictly to the authenticated user ID extracted from the verified JWT. Cross-patron loan or reservation querying is blocked by design.

---

## 3. Secret Management & API Key Policy

1. **Zero Key Bundling**: Athenaeum does not bundle, hardcode, or distribute API keys (Google Gemini, OpenAI, or SMTP credentials).
2. **Git Safeguards**: All `.env`, `.env.local`, and `*.db` patterns are included in `.gitignore`.
3. **Commit Scans**: All automated commits and release audits undergo regular regex scans for API keys (`AIzaSy*`, `sk-*`, raw passwords).
4. **Developer Responsibility**: Each developer and institutional maintainer must provide their own credentials in local environment files.

---

## 4. Reporting a Security Vulnerability

If you discover a security vulnerability in Athenaeum:

1. **Do Not File Public Issues**: Do not open a public GitHub Issue or post on public forums.
2. **Contact Repository Maintainers**: Send a detailed technical report to the repository administrator or author via private communication (e.g., GitHub Security Advisories or author profile).
3. **Report Contents**:
   - Step-by-step reproduction instructions.
   - Proof-of-concept payload or request trace.
   - Affected versions and endpoints.
   - Potential impact assessment.
4. **Response Timeline**: Maintainers will acknowledge receipt within 48 hours and work on a coordinated disclosure timeline.

---

## 5. Known Limitations & Threat Model Boundaries

- **Local Demonstrations**: In default development mode (`DEMO_MODE=true` or non-HTTPS local dev), cookies are not marked `Secure=True` so that local `localhost:5173` testing functions without SSL certificates. In production deployments, `COOKIE_SECURE=true` and an HTTPS reverse proxy (such as Nginx or Caddy) must be enabled.
- **Biometric & Financial Processing**: Biometric identity authentication (ADV-04) and real financial fine processing (ADV-05) are currently excluded from the core release and require separate institutional review before deployment.

