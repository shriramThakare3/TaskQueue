"""
api/routes.py
-------------
All task-related route handlers.
Mounted in main.py under the `/tasks` prefix.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from api.schemas import (
    TaskCreate, TaskResponse, TaskResult,
    TaskListResponse, HealthResponse,
)
from db.models import Task, TaskStatus
from db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """
    Liveness + readiness check.
    Pings the DB so Nginx / orchestrators can validate the whole stack.
    """
    try:
        db.execute(select(func.now()))
        db_status = "ok"
    except Exception as exc:
        logger.error("Health check DB error: %s", exc)
        db_status = "error"

    return HealthResponse(status="ok", db=db_status)


# ── Task CRUD ─────────────────────────────────────────────────────────────────

@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
    summary="Submit a new task",
)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    """
    Submit a task to the queue.

    The task will be picked up by the next available worker in priority order
    (higher `priority` value = processed sooner).
    """
    task = Task(
        id=str(uuid.uuid4()),
        name=payload.name,
        status=TaskStatus.PENDING,
        input_data=payload.input_data,
        priority=payload.priority,
        max_retries=payload.max_retries,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info("Task created: %s (name=%s, priority=%d)", task.id, task.name, task.priority)
    return task


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    tags=["tasks"],
    summary="List tasks with optional filters",
)
def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    name_filter: Optional[str]   = Query(None, alias="name",   description="Filter by task name"),
    limit: int  = Query(50,  ge=1, le=500),
    offset: int = Query(0,   ge=0),
    db: Session = Depends(get_db),
):
    """Return a paginated list of tasks, newest first."""
    query = select(Task)

    if status_filter:
        try:
            query = query.where(Task.status == TaskStatus(status_filter))
        except ValueError:
            valid = [s.value for s in TaskStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status_filter}'. Valid values: {valid}",
            )

    if name_filter:
        query = query.where(Task.name == name_filter)

    total_query = select(func.count()).select_from(query.subquery())
    total: int = db.execute(total_query).scalar_one()

    tasks = db.execute(
        query.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()

    return TaskListResponse(total=total, tasks=list(tasks))


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["tasks"],
    summary="Get full task details",
)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Fetch a single task by its UUID."""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    return task


@router.get(
    "/tasks/{task_id}/result",
    response_model=TaskResult,
    tags=["tasks"],
    summary="Poll for task result",
)
def get_task_result(task_id: str, db: Session = Depends(get_db)):
    """
    Lightweight endpoint for polling task completion.
    Returns status + result/error without the full task payload.
    """
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    return task


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["tasks"],
    summary="Delete a task",
)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """
    Delete a task record.
    Running tasks are NOT cancelled — they will finish but the record will be gone.
    """
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    db.delete(task)
    db.commit()
    logger.info("Task deleted: %s", task_id)
