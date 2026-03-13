"""
db/models.py
------------
ORM models. `Base.metadata.create_all(engine)` is called at startup
so tables are created automatically (no Alembic migration needed for dev).
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, DateTime, Enum as SAEnum,
    JSON, Text, func
)
from sqlalchemy.orm import DeclarativeBase


# ── Base ─────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Enum ─────────────────────────────────────────────────────────────────────
class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


# ── Task model ───────────────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"

    # Primary key — use a short UUID-like string for readability
    id = Column(String(36), primary_key=True, index=True)

    # Human-readable task type: "add", "sleep", "reverse", "file_write"
    name = Column(String(128), nullable=False, index=True)

    # Current lifecycle state
    status = Column(
        SAEnum(TaskStatus, name="taskstatus"),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Arbitrary JSON payload supplied by the caller
    input_data = Column(JSON, nullable=True)

    # Output JSON / text stored after execution
    result = Column(Text, nullable=True)

    # Error message if task failed
    error = Column(Text, nullable=True)

    # Higher number = higher priority (processed first)
    priority = Column(Integer, default=0, nullable=False, index=True)

    # Retry bookkeeping
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Timestamps (server-side defaults for portability)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} name={self.name} status={self.status}>"
