from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import init_db, get_db
from app.middleware.security import SecurityMiddleware
from app.schemas import HealthResponse
from app import models  # noqa: F401
from app.routers.auth import router as auth_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB (WAL configuration + table creation) before serving requests
    init_db()
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


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying application status and database connectivity.
    """
    db.execute(text("SELECT 1;"))
    return HealthResponse(
        status="healthy",
        project_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        database="connected",
    )
