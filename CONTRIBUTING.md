# Athenaeum: Contributor Guidelines & Code of Engineering

Thank you for your interest in contributing to **Athenaeum**! This project is an enterprise-grade academic library management platform with strict requirements for data integrity, architectural consistency, and test coverage.

Please read this guide carefully before submitting issues or pull requests.

---

## 1. Development Principles & Code Standards

Every contribution to Athenaeum must satisfy the following core principles:

1. **Type Safety Across Both Tiers**:
   - Backend code must pass type validation using Pydantic v2 schemas and modern Python type hints (`Optional`, `Union`, `List`, `Dict`).
   - Frontend code must be written in TypeScript with zero untyped `any` annotations. All props and API payloads must have explicit interfaces in `frontend/src/types/library.ts`.
2. **Deterministic Architecture**:
   - Never implement features that rely solely on external cloud APIs without a deterministic local fallback.
   - All AI integrations must operate cleanly in offline/fallback mode when API keys are absent.
3. **Database & Migration Safety**:
   - Never modify protected baseline databases (`backend/library.db`, `backend/library_demo.db`).
   - Schema modifications must be encapsulated in an Alembic migration script under `backend/alembic/versions/` with both `upgrade()` and `downgrade()` methods.

---

## 2. Branching & Workflow Strategy

- **Default Development Branch**: `feature/ai-agent-upgrade` or feature branches branched from `main`.
- **Branch Naming Conventions**:
  - `feat/feature-name` for new user-facing capabilities.
  - `fix/bug-description` for bug repairs and stability enhancements.
  - `docs/topic-name` for documentation improvements.
  - `refactor/subsystem-name` for non-functional code restructurings.
- **Commit Messages**: Follow Conventional Commits format:
  ```
  feat(circulation): add QR collection token expiration verification
  fix(copilot): prevent cross-patron query context leaks in tool caller
  docs(api): document course reserves endpoints and schemas
  ```

---

## 3. Pull Request Submission Checklist

Before opening a Pull Request, verify that your branch satisfies all criteria:

- [ ] **Backend Tests Pass**: Run `pytest backend/tests -v` and ensure all tests pass (0 failures).
- [ ] **Frontend Production Build Passes**: Run `npm --prefix frontend run build` and ensure Vite and `tsc` complete without errors.
- [ ] **Zero Hardcoded Secrets**: Ensure no API keys, private passwords, or local file paths are committed.
- [ ] **Database Integrity**: Verify that protected SQLite hashes (`backend/library.db`) are unchanged.
- [ ] **Documentation Updated**: If you add an endpoint, update `docs/TECHNICAL_DOCUMENTATION.md` and `docs/api-reference.md`.

---

## 4. Code Formatting & Tooling

### Backend
- Follow PEP 8 style conventions.
- Organize imports: standard library first, third-party libraries second, internal application modules (`from app...`) third.
- Use explicit docstrings for all router endpoints, domain service functions, and helper utilities.

### Frontend
- Keep React components focused and modular under `frontend/src/components/`.
- Use functional components with typed props:
  ```typescript
  interface BookCardProps {
    book: Book;
    onSelect: (book: Book) => void;
  }
  export const BookCard: React.FC<BookCardProps> = ({ book, onSelect }) => { ... };
  ```
- Store shared CSS styles in `frontend/src/index.css` using existing CSS variable design tokens.

