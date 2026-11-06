import sys
from pathlib import Path

# Ensure backend root is always in sys.path
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db, Base, engine
from app.core.dependencies import limiter
from app.routers import auth, specialties, doctors, schedules, appointments, chat, admin
from app.tasks.reminders import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: initialize DB and manage background scheduler."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    # Start APScheduler background reminder system
    start_scheduler()
    yield
    # Clean shutdown of scheduler
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    description="MediDesk Agent – AI-Powered Hospital Appointment Booking System Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(specialties.router)
app.include_router(doctors.router)
app.include_router(schedules.router)
app.include_router(appointments.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint that verifies application and database connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": db_status
    }
