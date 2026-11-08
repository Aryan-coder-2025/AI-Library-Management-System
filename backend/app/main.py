import sys
from pathlib import Path

# Ensure backend root is on sys.path regardless of whether uvicorn is launched from repo root or backend/
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import init_db, get_db, validate_demo_database
from app.middleware.security import SecurityMiddleware
from app.schemas import HealthResponse
from app import models  # noqa: F401
from app.routers.auth import router as auth_router
from app.routers.catalogue import router as catalogue_router
from app.routers.loans import router as loans_router
from app.routers.notifications import router as notifications_router
from app.routers.semantic import router as semantic_router
from app.routers.copilot import router as copilot_router
from app.routers.spaces import router as spaces_router
from app.routers.spatial import router as spatial_router
from app.routers.knowledge import router as knowledge_router
from app.routers.research import router as research_router
from app.routers.holds import router as holds_router
from app.routers.courses import router as courses_router
from app.routers.circulation_ops import router as circulation_ops_router
from app.routers.intelligence import router as intelligence_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In demo mode, validate published demo database without modifying it or running migrations.
    # In standard mode, initialize DB (WAL configuration + migrations) before serving requests.
    curr_settings = get_settings()
    if curr_settings.DEMO_MODE:
        validate_demo_database(curr_settings.DATABASE_URL)
    else:
        init_db(curr_settings.DATABASE_URL)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for AI Library Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# Custom Origin + CSRF Double-Submit Cookie verification middleware
app.add_middleware(SecurityMiddleware)

# Standard CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register application routers
app.include_router(auth_router)
app.include_router(catalogue_router)
app.include_router(loans_router)
app.include_router(notifications_router)
app.include_router(semantic_router)
app.include_router(copilot_router)
app.include_router(spaces_router)
app.include_router(spatial_router)
app.include_router(knowledge_router)
app.include_router(research_router)
app.include_router(holds_router)
app.include_router(courses_router)
app.include_router(circulation_ops_router)
app.include_router(intelligence_router)


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying application status and database connectivity.
    """
    db.execute(text("SELECT 1;"))
    curr_settings = get_settings()
    return HealthResponse(
        status="healthy",
        project_name=curr_settings.PROJECT_NAME,
        environment="demo" if curr_settings.DEMO_MODE else curr_settings.ENVIRONMENT,
        database="connected",
        demo_mode=curr_settings.DEMO_MODE,
    )
