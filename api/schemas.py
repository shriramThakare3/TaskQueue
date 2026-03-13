"""
api/schemas.py
--------------
Pydantic v2 models used for request validation and response serialisation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request bodies ────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    """Payload for POST /tasks."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        examples=["add", "sleep", "reverse", "file_write"],
        description="Task type name — must match a registered handler in tasks.py",
    )
    input_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Arbitrary JSON input forwarded to the task handler",
        examples=[{"a": 3, "b": 7}],
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Higher value = processed sooner",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max automatic retry attempts on failure",
    )


# ── Response bodies ───────────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    """Full task record returned to the client."""
    id: str
    name: str
    status: str
    input_data: Optional[dict[str, Any]]
    result: Optional[str]
    error: Optional[str]
    priority: int
    retry_count: int
    max_retries: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskResult(BaseModel):
    """Lightweight result-only view for GET /tasks/{id}/result."""
    id: str
    name: str
    status: str
    result: Optional[str]
    error: Optional[str]

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated task list wrapper."""
    total: int
    tasks: list[TaskResponse]


class HealthResponse(BaseModel):
    status: str
    db: str
    version: str = "1.0.0"
