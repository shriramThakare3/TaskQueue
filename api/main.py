"""
api/main.py
-----------
FastAPI application factory.
Started by Gunicorn in the api container:
    gunicorn api.main:app -k uvicorn.workers.UvicornWorker
"""
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.config import settings
from db.models import Base
from db.session import engine

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    application = FastAPI(
        title="Task Queue API",
        description=(
            "A mini Celery clone — submit tasks via REST, workers execute them "
            "asynchronously, results are stored in PostgreSQL."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS (open for dev; restrict in production)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount all routes (tasks + health)
    application.include_router(router)

    @application.on_event("startup")
    def on_startup():
        logger.info("Creating DB tables if they don't exist …")
        Base.metadata.create_all(bind=engine)
        logger.info("API startup complete — env=%s", settings.APP_ENV)

    return application


app = create_app()
