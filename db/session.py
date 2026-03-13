"""
db/session.py
-------------
Creates the SQLAlchemy engine and session factory.
`get_db()` is the FastAPI dependency for DB access.
`get_db_session()` is a context manager used by the worker.
"""
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.config import settings

logger = logging.getLogger(__name__)

# ── Engine ───────────────────────────────────────────────────────────────────
# pool_pre_ping ensures stale connections are recycled automatically
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=(settings.APP_ENV == "development"),
)

# ── Session factory ──────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # safe for background workers
)


# ── FastAPI dependency ───────────────────────────────────────────────────────
def get_db():
    """Yield a DB session; always close on exit."""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Worker context manager ───────────────────────────────────────────────────
@contextmanager
def get_db_session():
    """Context manager for use outside FastAPI (e.g., worker processes)."""
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("DB session error: %s", exc)
        raise
    finally:
        db.close()
