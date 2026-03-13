"""
worker/tasks.py
---------------
Task handler registry.

Each handler is a plain Python callable:
    def handler(input_data: dict) -> str

Register new tasks by adding them to TASK_REGISTRY at the bottom.
The worker looks up the task `name` field in this registry.
"""
import json
import logging
import os
import time

logger = logging.getLogger(__name__)


# ── Individual task implementations ───────────────────────────────────────────

def task_add(input_data: dict) -> str:
    """
    Add two numbers.
    Expected input: {"a": <number>, "b": <number>}
    """
    a = input_data.get("a", 0)
    b = input_data.get("b", 0)
    result = a + b
    logger.debug("add: %s + %s = %s", a, b, result)
    return json.dumps({"result": result, "expression": f"{a} + {b} = {result}"})


def task_sleep(input_data: dict) -> str:
    """
    Sleep for N seconds (simulates long-running work).
    Expected input: {"seconds": <float>}
    """
    seconds = float(input_data.get("seconds", 1))
    seconds = min(seconds, 30)  # cap to 30s for safety
    logger.debug("sleep: sleeping for %ss", seconds)
    time.sleep(seconds)
    return json.dumps({"slept_for": seconds, "message": f"Slept {seconds}s successfully"})


def task_reverse(input_data: dict) -> str:
    """
    Reverse a string.
    Expected input: {"text": "<string>"}
    """
    text = input_data.get("text", "")
    reversed_text = text[::-1]
    logger.debug("reverse: '%s' → '%s'", text, reversed_text)
    return json.dumps({"original": text, "reversed": reversed_text})


def task_file_write(input_data: dict) -> str:
    """
    Write content to a temp file and return the path.
    Expected input: {"filename": "<name>", "content": "<text>"}
    """
    filename = input_data.get("filename", "output.txt")
    content  = input_data.get("content", "")

    # Sanitise filename — no path traversal
    safe_name = os.path.basename(filename)
    output_dir = "/tmp/taskqueue_files"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, safe_name)
    with open(filepath, "w") as f:
        f.write(content)

    size = os.path.getsize(filepath)
    logger.debug("file_write: wrote %d bytes to %s", size, filepath)
    return json.dumps({"filepath": filepath, "bytes_written": size, "filename": safe_name})


def task_fibonacci(input_data: dict) -> str:
    """
    Compute the Nth Fibonacci number.
    Expected input: {"n": <int>}
    """
    n = int(input_data.get("n", 10))
    n = min(n, 1000)  # cap to avoid excessive compute

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b

    return json.dumps({"n": n, "fibonacci": a})


def task_word_count(input_data: dict) -> str:
    """
    Count words, lines, and characters in a string.
    Expected input: {"text": "<string>"}
    """
    text = input_data.get("text", "")
    words = len(text.split())
    lines = len(text.splitlines())
    chars = len(text)
    return json.dumps({"words": words, "lines": lines, "characters": chars})


# ── Registry ──────────────────────────────────────────────────────────────────
# Map task `name` → handler function
TASK_REGISTRY: dict[str, callable] = {
    "add":        task_add,
    "sleep":      task_sleep,
    "reverse":    task_reverse,
    "file_write": task_file_write,
    "fibonacci":  task_fibonacci,
    "word_count": task_word_count,
}
