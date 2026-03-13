"""
worker/worker.py
----------------
Background worker process.

Architecture
────────────
* A supervisor (main thread) spawns N worker threads (WORKER_COUNT).
* Each thread independently polls PostgreSQL for the highest-priority
  PENDING task, locks it with SELECT … FOR UPDATE SKIP LOCKED, transitions
  it to RUNNING, executes the handler, then writes the result back.
* SKIP LOCKED prevents multiple workers from picking the same task.
* On handler failure the task is retried up to max_retries times before
  being marked FAILED.

Run directly:
    python -m worker.worker
Or via Docker Compose (see docker-compose.yml).
"""
import logging
import sys
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from core.config import settings
from db.models import Base, Task, TaskStatus
from db.session import SessionLocal, engine
from worker.tasks import TASK_REGISTRY

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s (%(threadName)s) — %(message)s",
)
logger = logging.getLogger(__name__)


# ── DB init ───────────────────────────────────────────────────────────────────
def init_db():
    """Create tables if they don't exist (idempotent)."""
    logger.info("Initialising DB schema …")
    Base.metadata.create_all(bind=engine)
    logger.info("DB schema ready.")


# ── Core execution logic ──────────────────────────────────────────────────────
def fetch_and_lock_task(db) -> Task | None:
    """
    Atomically grab the next PENDING task ordered by:
      1. priority DESC  (higher number = more urgent)
      2. created_at ASC (FIFO within same priority)

    SKIP LOCKED means other workers concurrently running this query will
    skip over any row already held by us — zero contention.
    """
    stmt = (
        select(Task)
        .where(Task.status == TaskStatus.PENDING)
        .order_by(Task.priority.desc(), Task.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return db.execute(stmt).scalars().first()


def mark_running(db, task: Task):
    db.execute(
        update(Task)
        .where(Task.id == task.id)
        .values(status=TaskStatus.RUNNING, updated_at=datetime.now(timezone.utc))
    )
    db.commit()


def mark_done(db, task: Task, result: str):
    db.execute(
        update(Task)
        .where(Task.id == task.id)
        .values(
            status=TaskStatus.DONE,
            result=result,
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    logger.info("Task DONE: %s", task.id)


def mark_failed(db, task: Task, error: str):
    db.execute(
        update(Task)
        .where(Task.id == task.id)
        .values(
            status=TaskStatus.FAILED,
            error=error,
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    logger.warning("Task FAILED: %s — %s", task.id, error)


def requeue_for_retry(db, task: Task, error: str):
    """Reset to PENDING so it will be picked up again."""
    new_retry = task.retry_count + 1
    db.execute(
        update(Task)
        .where(Task.id == task.id)
        .values(
            status=TaskStatus.PENDING,
            retry_count=new_retry,
            error=f"Retry {new_retry}: {error}",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    logger.info("Task %s scheduled for retry %d/%d", task.id, new_retry, task.max_retries)


def execute_task(task: Task) -> str:
    """
    Look up the task handler in the registry and call it.
    Raises ValueError if the task name is unknown.
    """
    handler = TASK_REGISTRY.get(task.name)
    if handler is None:
        available = list(TASK_REGISTRY.keys())
        raise ValueError(
            f"Unknown task '{task.name}'. "
            f"Available tasks: {available}"
        )
    input_data = task.input_data or {}
    return handler(input_data)


# ── Worker loop ───────────────────────────────────────────────────────────────
def worker_loop(worker_id: int, stop_event: threading.Event):
    """
    Main loop for a single worker thread.
    Polls the DB, executes tasks, sleeps when idle.
    """
    logger.info("Worker %d started.", worker_id)

    while not stop_event.is_set():
        db = SessionLocal()
        try:
            task = fetch_and_lock_task(db)

            if task is None:
                # Nothing to do — sleep and try again
                db.close()
                time.sleep(settings.WORKER_POLL_INTERVAL)
                continue

            logger.info(
                "Worker %d picked task %s (name=%s, priority=%d, retry=%d/%d)",
                worker_id, task.id, task.name, task.priority,
                task.retry_count, task.max_retries,
            )

            mark_running(db, task)

            try:
                result = execute_task(task)
                mark_done(db, task, result)

            except Exception as exc:
                error_msg = str(exc)
                logger.error("Worker %d — task %s raised: %s", worker_id, task.id, error_msg)

                # Retry or permanently fail
                if task.retry_count < task.max_retries:
                    requeue_for_retry(db, task, error_msg)
                else:
                    mark_failed(db, task, error_msg)

        except Exception as outer_exc:
            # Catch DB errors / unexpected crashes so the worker doesn't die
            logger.exception("Worker %d — unexpected error: %s", worker_id, outer_exc)
        finally:
            db.close()

    logger.info("Worker %d stopped.", worker_id)


# ── Supervisor ────────────────────────────────────────────────────────────────
def run_workers():
    """Spawn WORKER_COUNT threads and keep them alive until KeyboardInterrupt."""
    init_db()

    count = settings.WORKER_COUNT
    logger.info("Starting %d worker thread(s) …", count)

    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    for i in range(1, count + 1):
        t = threading.Thread(
            target=worker_loop,
            args=(i, stop_event),
            name=f"Worker-{i}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    try:
        # Keep the main thread alive; watchdog log every 60s
        while True:
            alive = sum(1 for t in threads if t.is_alive())
            logger.debug("Supervisor heartbeat — %d/%d threads alive", alive, count)
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received — stopping workers …")
        stop_event.set()
        for t in threads:
            t.join(timeout=10)
        logger.info("All workers stopped. Bye.")


if __name__ == "__main__":
    run_workers()
