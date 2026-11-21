from __future__ import annotations

from typing import Callable

from .jobs import InMemoryJobStore, Job


def run_job(store: InMemoryJobStore, job_id: str, handler: Callable[[Job], None]) -> Job:
    """Execute one claimed job with terminal failure capture."""
    job = store.transition(job_id, "running")
    try:
        handler(job)
    except Exception as exc:
        return store.transition(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
    return store.transition(job_id, "succeeded")
