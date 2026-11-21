from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Literal
from uuid import uuid4

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(), "failed": set(), "cancelled": set(),
}


@dataclass
class Job:
    job_id: str
    kind: str
    status: JobStatus = "queued"
    payload: dict = field(default_factory=dict)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryJobStore:
    """Thread-safe local adapter; production can implement the same surface on Redis."""
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(self, kind: str, payload: dict | None = None) -> Job:
        with self._lock:
            job = Job(uuid4().hex, kind, payload=payload or {})
            self._jobs[job.job_id] = job
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def transition(self, job_id: str, status: JobStatus, error: str | None = None) -> Job:
        with self._lock:
            job = self._jobs[job_id]
            if status not in _TRANSITIONS[job.status]:
                raise ValueError(f"invalid job transition {job.status}->{status}")
            job.status, job.error, job.updated_at = status, error, datetime.now(timezone.utc)
            return job

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())
