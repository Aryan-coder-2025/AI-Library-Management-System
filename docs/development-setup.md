# Development Environment & Setup Guide

**Document Version:** 1.0.0  
**Operating System:** Windows 10 / Windows 11 (PowerShell)  
**Python Runtime:** Python 3.11.x  
**Node.js Runtime:** Node.js v20+ / v22+ (npm v10+)  

---

## 1. Prerequisites & System Requirements

Ensure the following tools are installed on your Windows machine:
- **Python 3.11** (Verify via `python --version`)
- **Node.js** (Verify via `node --version`)
- **PowerShell 7 (pwsh)** or standard Windows PowerShell 5.1
- **Git** (Verify via `git --version`)

---

## 2. Repository Cloning & Branch Setup

Clone the repository and verify that you are on the active feature branch:

```powershell
git clone https://github.com/Aryan-coder-2025/AI-Library-Management-System.git
cd AI-Library-Management-System

# Confirm current branch is feature/aryan-ai-library-system
git branch
```

---

## 3. Backend Environment Setup

The backend uses a virtual environment located in `backend/venv`.

### Step 1: Initialize Virtual Environment
If `backend/venv` is not yet created:
```powershell
cd backend
python -m venv venv
```

### Step 2: Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install torch sentence-transformers scikit-learn
```

### Step 4: Configure Environment Variables
Create a local `.env` file in the repository root by copying `.env.example`:
```powershell
cd ..
Copy-Item .env.example .env
```
Key configuration items in `.env`:
- `PROJECT_NAME="AI Library Management System"`
- `JWT_SECRET_KEY="<your-secret-key-at-least-32-chars>"`
- `ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]`
- `DATABASE_URL`: Leave commented out or unset to use the default hardened SQLite database path (`backend/library.db`).

---

## 4. Database Setup & Demonstration Seeder

The system is configured to use `backend/library.db` by default.

### Inspecting Current Database Records
To verify whether the database is already populated without making modifications:
```powershell
cd backend
.\venv\Scripts\python.exe -m app.seed_demo --inspect
```

### Seeding Demonstration Data (Idempotent)
If setting up a fresh environment or adding demonstration records:
```powershell
cd backend
.\venv\Scripts\python.exe -m app.seed_demo
```
The seeder idempotently populates:
- 15 academic monographs with ISBNs and descriptions across Computer Science, AI, Physics, Mathematics, and Cybersecurity.
- 31 physical barcode copies (30 available, 1 under maintenance).
- Demonstration student and librarian user accounts.
- Active and historical circulation loans.
- Precomputed 384-dimensional dense vector embeddings.

---

## 5. Frontend Environment Setup

The frontend is built with React 19, TypeScript, and Vite.

### Step 1: Install Node Dependencies
Open a PowerShell terminal in the `frontend/` directory:
```powershell
cd frontend
npm install
```

### Step 2: Verify Production Build
Ensure that TypeScript types and Vite bundling pass cleanly:
```powershell
npm run build
```

---

## 6. Running the Development Services

Run the frontend and backend in two separate PowerShell terminal windows:

### Terminal 1: Backend API (Uvicorn)
```powershell
cd c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Verification:* Navigate to `http://127.0.0.1:8000/api/health` in your browser. Expected response:
```json
{"status":"healthy","project_name":"AI Library Management System","environment":"development","database":"connected"}
```

### Terminal 2: Frontend Web Client (Vite)
```powershell
cd c:\Users\aryan\OneDrive\Desktop\AI-Library-Management-System\frontend
npm run dev
```
*Verification:* Open `http://localhost:5173` in your browser. The login interface should appear.

---

## 7. Verified Demonstration Login Accounts

The following credentials are created by the demonstration seeder ([`backend/app/seed_demo.py`](file:///c:/Users/aryan/OneDrive/Desktop/AI-Library-Management-System/backend/app/seed_demo.py)):

| Role | Email | Password | Primary Accessible Features |
| :--- | :--- | :--- | :--- |
| **Student** | `demo_student@library.local` | `StudentDemo123!` | Catalogue Search, Category Filters, AI Semantic Vector Search, My Loans (Active & Historical), AI Copilot Drawer, Student Guided Tour |
| **Librarian (Staff)** | `demo_librarian@library.local` | `LibrarianDemo123!` | Full Student Features + Catalogue Management (Add/Edit/Archive Books), Barcode Inventory Desk, Circulation Check-Out & Return Desk, Vector Embeddings Pipeline Status & Reindexing, Staff Guided Tour |

---

## 8. Executing Automated Tests

### Run Backend Unit & Integration Tests (135 Tests)
```powershell
cd backend
cmd /c "set PYTHONPATH=.&& .\venv\Scripts\python.exe -m pytest -v"
```

### Run Targeted Subsystem Tests
- **Database Configuration & Path Resolution:**
  ```powershell
  cmd /c "set PYTHONPATH=.&& .\venv\Scripts\python.exe -m pytest tests/test_config.py -v"
  ```
- **Authentication & Security:**
  ```powershell
  cmd /c "set PYTHONPATH=.&& .\venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_security.py -v"
  ```
- **Circulation & Database Integrity:**
  ```powershell
  cmd /c "set PYTHONPATH=.&& .\venv\Scripts\python.exe -m pytest tests/test_loans.py tests/test_db_integrity.py -v"
  ```
- **Semantic Vector Search & Recommendations:**
  ```powershell
  cmd /c "set PYTHONPATH=.&& .\venv\Scripts\python.exe -m pytest tests/test_semantic.py -v"
  ```
- **AI Copilot & Intent Routing:**
  ```powershell
  cmd /c "set PYTHONPATH=.&& .\venv\Scripts\python.exe -m pytest tests/test_copilot.py -v"
  ```

