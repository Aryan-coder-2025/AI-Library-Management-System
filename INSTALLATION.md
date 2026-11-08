# Athenaeum: Local Installation & Setup Guide

This guide provides executable, step-by-step instructions for installing, configuring, verifying, and running **Athenaeum** on a local development workstation.

The primary supported platform is **Windows 10/11 using PowerShell**. Linux (Ubuntu/Debian) and macOS (macOS 13+) instructions are provided where applicable.

---

## 1. Prerequisites & Environment Verification

Before proceeding, ensure your development machine meets the minimum software requirements:

| Tool | Minimum Version | Verified Compatible Version | Check Command (PowerShell) |
|---|---|---|---|
| **Python** | `3.10+` | `3.11.x` or `3.12.x` | `python --version` |
| **Node.js** | `18.x+` | `20.x` or `22.x` | `node --version` |
| **npm** | `9.x+` | `10.x+` | `npm --version` |
| **Git** | `2.30+` | `2.40+` | `git --version` |

Verify all tools in PowerShell:
```powershell
python --version
node --version
npm --version
git --version
```

---

## 2. Repository Cloning & Directory Layout

Clone the repository and enter the project root directory:

```powershell
git clone https://github.com/aryan2025/AI-Library-Management-System.git
cd AI-Library-Management-System
```

The repository structure comprises two primary application directories:
- `backend/`: FastAPI application, Alembic migrations, test suite, and SQLite databases.
- `frontend/`: React 19 single-page application, Vite configuration, and styles.

---

## 3. Backend Setup & Virtual Environment

### 3.1 Create and Activate Python Virtual Environment

On Windows PowerShell:
```powershell
# Create virtual environment in backend/venv
python -m venv backend\venv

# Set execution policy if PowerShell script execution is restricted
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate the virtual environment
.\backend\venv\Scripts\Activate.ps1
```

*(On Linux / macOS: `python3 -m venv backend/venv && source backend/venv/bin/activate`)*

### 3.2 Upgrade Pip & Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

Verify backend installation:
```powershell
python -c "import fastapi, sqlalchemy, pydantic; print('Backend runtime dependencies OK')"
```

---

## 4. Environment Configuration (`.env`)

Athenaeum uses a hierarchical environment configuration system. The application discovers `.env` files in the following order:
1. Project root `.env` (base configuration)
2. `backend/.env` (backend-specific overrides)
3. Working directory `.env`

### 4.1 Create Local Environment File

Copy the template from the root directory:
```powershell
# In project root:
Copy-Item .env.example .env
```

Open `.env` in your text editor. At minimum, ensure the following keys are set:

```ini
PROJECT_NAME="AI Library Management System"
ENVIRONMENT="development"
DEBUG=true
DEMO_MODE=false

# Security Keys (Generate random 32-byte hex strings for production)
JWT_SECRET_KEY="dev-secret-key-at-least-32-chars-long-for-testing"
SPACES_QR_SECRET_KEY="distinct-spaces-qr-key-at-least-32-chars-long"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=480

# CORS Whitelist
ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

# Database URL (Default development baseline)
DATABASE_URL="sqlite:///./backend/library.db"

# AI Copilot Configuration (Optional)
LLM_PROVIDER="auto"
LLM_MODEL_NAME="gemini-3.1-flash-lite-preview"
# To enable live Google Gemini inference:
# GEMINI_API_KEY="your-gemini-api-key-here"

# Transactional Email (Optional - defaults to mock logging)
EMAIL_ENABLED=false
```

> [!IMPORTANT]
> **Database Protection Rule**: The repository includes pre-populated protected canonical databases (`backend/library.db` and `backend/library_demo.db`). In `development` mode with `DEMO_MODE=false`, the server operates safely without overwriting canonical seeds. If you intend to run destructive schema migrations, configure a disposable local database:
> ```ini
> DATABASE_URL="sqlite:///./backend/library_local.db"
> ```

---

## 5. Frontend Setup & Dependencies

In a separate terminal window (or without virtual environment active):

```powershell
cd c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System\frontend

# Install frontend npm dependencies
npm install
```

Verify frontend compilation:
```powershell
npm run build
```
The build should complete with 0 errors and transform all 147 modules into `frontend/dist/`.

---

## 6. Running the Application Locally

To run the complete Athenaeum system, start both the backend server and frontend development server.

### 6.1 Start the FastAPI Backend Server

Open Terminal 1 (PowerShell):
```powershell
cd c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System
.\backend\venv\Scripts\Activate.ps1

# Start Uvicorn ASGI server on port 8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend API will be accessible at:
- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Documentation**: `http://127.0.0.1:8000/docs`
- **ReDoc API Documentation**: `http://127.0.0.1:8000/redoc`

### 6.2 Start the Vite Frontend Server

Open Terminal 2 (PowerShell):
```powershell
cd c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System\frontend

# Start Vite dev server
npm run dev
```
The frontend UI will be accessible at:
- **Frontend URL**: `http://localhost:5173`

---

## 7. Configuring AI Providers (Gemini / OpenAI / Ollama)

Athenaeum does **not** bundle API keys. By default, the system operates in **Deterministic Fallback Mode**, providing verified answers grounded in live catalog holdings and library policies.

### 7.1 Using Google Gemini (Google AI Studio)
1. Visit [Google AI Studio](https://aistudio.google.com/) and generate an API key.
2. In `backend/.env` (or root `.env`), set:
   ```ini
   LLM_PROVIDER=auto
   GEMINI_API_KEY=your-gemini-api-key-here
   LLM_MODEL_NAME=gemini-3.1-flash-lite-preview
   ```
3. Restart the backend Uvicorn process.
4. Verify by opening the Copilot Drawer and asking a research question. The Model Comparison Studio will display the **Google Gemini Live API** badge.

### 7.2 Using OpenAI
1. In `backend/.env`, set:
   ```ini
   OPENAI_API_KEY=sk-your-openai-api-key
   ```
2. The Model Comparison Studio will automatically unlock live GPT-4o queries.

### 7.3 Using Local Ollama (Offline / Free)
1. Download and install [Ollama](https://ollama.com/).
2. Pull a model (e.g., `ollama pull llama3.2`).
3. Ensure the daemon is running on port 11434 (`http://localhost:11434`).
4. In `backend/.env`, set:
   ```ini
   LLM_API_URL=http://localhost:11434/v1
   ```

---

## 8. Verifying the Installation via Automated Tests

Execute the full backend test suite to verify system integrity:

```powershell
cd c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System
.\backend\venv\Scripts\Activate.ps1

# Run full backend test suite (395 tests)
pytest backend\tests -v
```

Expected output:
```
393 passed, 2 skipped in ~145s
```
*(The 2 skipped tests represent non-administrative Windows symlink permission assertions, which are expected in standard user-mode development).*

---

## 9. Common Troubleshooting

### Issue: `Port 8000 already in use`
- **Cause**: An existing Uvicorn or Python process is still bound to port 8000.
- **Fix (PowerShell)**:
  ```powershell
  Get-Process -Name python | Stop-Process -Force
  ```

### Issue: `Missing SPACES_QR_SECRET_KEY error on startup`
- **Cause**: `SPACES_QR_SECRET_KEY` is either missing or identical to `JWT_SECRET_KEY`.
- **Fix**: Open `.env` and set two distinct 32-character keys for `JWT_SECRET_KEY` and `SPACES_QR_SECRET_KEY`.

### Issue: `oxlint: Cannot find native binding on Windows`
- **Cause**: Optional binary binding missing in local npm node_modules.
- **Fix**: Use `npm run build` directly. TypeScript type-checking (`tsc -b`) executes independently and provides 100% type coverage.
