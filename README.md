# Task Queue System

A production-style asynchronous task queue built with FastAPI, PostgreSQL, and background workers — containerised with Docker Compose.

---

## Architecture

```
Client → Nginx (port 80) → FastAPI/Gunicorn (port 8000) → PostgreSQL
                                                              ↑
                                           Worker threads (poll & execute)
```

| Service  | Technology            | Role                                    |
|----------|-----------------------|-----------------------------------------|
| `nginx`  | Nginx 1.25            | Reverse proxy, load balancing           |
| `api`    | FastAPI + Gunicorn    | REST API, task submission & status      |
| `worker` | Python threading      | Poll DB, execute tasks, store results   |
| `db`     | PostgreSQL 16         | Persistent task store                   |

---

## Quick Start

### Prerequisites
- Docker ≥ 24
- Docker Compose v2

### 1. Clone & configure

```bash
git clone <repo>
cd taskqueue
cp .env .env.local   # optional: customise values
```

### 2. Start all services

```bash
docker compose up --build
```

Services start in order: `db` → `api` → `worker` → `nginx`

### 3. Verify everything is running

```bash
docker compose ps
curl http://localhost/health
# → {"status":"ok","db":"ok","version":"1.0.0"}
```

---

## API Reference

Base URL: `http://localhost` (via Nginx)

Interactive docs: `http://localhost/docs`

### Submit a task

```bash
# Add two numbers
curl -s -X POST http://localhost/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "add", "input_data": {"a": 21, "b": 21}, "priority": 5}'

# Sleep task (simulates background work)
curl -s -X POST http://localhost/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "sleep", "input_data": {"seconds": 3}}'

# Reverse a string
curl -s -X POST http://localhost/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "reverse", "input_data": {"text": "Hello World"}}'

# Write a file
curl -s -X POST http://localhost/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "file_write", "input_data": {"filename": "hello.txt", "content": "Hi from task queue!"}}'

# Fibonacci
curl -s -X POST http://localhost/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "fibonacci", "input_data": {"n": 30}, "priority": 10}'
```

### Poll for result

```bash
TASK_ID="<uuid from response above>"

# Full details
curl http://localhost/tasks/$TASK_ID

# Just the result
curl http://localhost/tasks/$TASK_ID/result
```

### List tasks

```bash
# All tasks
curl "http://localhost/tasks"

# Filter by status
curl "http://localhost/tasks?status=pending"
curl "http://localhost/tasks?status=done"
curl "http://localhost/tasks?status=failed"

# Filter by name
curl "http://localhost/tasks?name=add"

# Pagination
curl "http://localhost/tasks?limit=10&offset=20"
```

### Delete a task

```bash
curl -X DELETE http://localhost/tasks/$TASK_ID
```

---

## Available Task Types

| Name         | Input fields                         | Description                          |
|--------------|--------------------------------------|--------------------------------------|
| `add`        | `a`, `b` (numbers)                   | Returns a + b                        |
| `sleep`      | `seconds` (float, max 30)            | Simulates long-running work          |
| `reverse`    | `text` (string)                      | Reverses the input string            |
| `file_write` | `filename`, `content` (strings)      | Writes content to /tmp/taskqueue_files |
| `fibonacci`  | `n` (int, max 1000)                  | Returns the Nth Fibonacci number     |
| `word_count` | `text` (string)                      | Returns word/line/char counts        |

---

## Scaling

### Scale workers (multiple worker processes)

```bash
docker compose up --scale worker=4
```

Each worker uses `SELECT ... FOR UPDATE SKIP LOCKED` to prevent double-processing.

### Scale API (multiple Gunicorn instances behind Nginx)

```bash
docker compose up --scale api=3
```

Nginx round-robins across all `api` replicas automatically.

---

## Configuration (.env)

| Variable               | Default       | Description                          |
|------------------------|---------------|--------------------------------------|
| `POSTGRES_USER`        | `taskuser`    | DB username                          |
| `POSTGRES_PASSWORD`    | `taskpass`    | DB password                          |
| `POSTGRES_DB`          | `taskqueue`   | DB name                              |
| `WORKER_POLL_INTERVAL` | `2.0`         | Seconds between DB polls (per worker)|
| `WORKER_COUNT`         | `2`           | Worker threads per container         |
| `WORKER_MAX_RETRIES`   | `3`           | Default retry limit per task         |
| `LOG_LEVEL`            | `INFO`        | Python logging level                 |

---

## Retry Logic

Tasks are retried automatically on failure:
- Each task has a `max_retries` field (default: 3, set per-task at submission).
- On failure: `retry_count` increments and status resets to `PENDING`.
- After `max_retries` exhausted: status is set to `FAILED` with the error message.

---

## Development

### Run locally without Docker

```bash
# 1. Start only PostgreSQL
docker compose up db -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set env vars
export $(cat .env | xargs)
export POSTGRES_HOST=localhost

# 4. Start API
uvicorn api.main:app --reload --port 8000

# 5. Start worker (separate terminal)
python -m worker.worker
```

### View logs

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f nginx
```

### Connect to DB

```bash
docker compose exec db psql -U taskuser -d taskqueue
# Then: SELECT id, name, status, priority FROM tasks ORDER BY created_at DESC LIMIT 20;
```

### Tear down

```bash
docker compose down          # keep volumes
docker compose down -v       # also delete DB data
```
