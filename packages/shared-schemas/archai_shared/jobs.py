from __future__ import annotations

import json
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

    def as_dict(self) -> dict:
        return {"job_id": self.job_id, "kind": self.kind, "status": self.status, "payload": self.payload,
                "error": self.error, "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat()}

    @classmethod
    def from_dict(cls, value: dict) -> "Job":
        return cls(job_id=value["job_id"], kind=value["kind"], status=value["status"], payload=value["payload"],
                   error=value.get("error"), created_at=datetime.fromisoformat(value["created_at"]),
                   updated_at=datetime.fromisoformat(value["updated_at"]))


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

    def pop_queued(self) -> Job | None:
        """Claim one queued job atomically for a local worker."""
        with self._lock:
            for job in self._jobs.values():
                if job.status == "queued":
                    job.status = "running"
                    job.updated_at = datetime.now(timezone.utc)
                    return job
        return None


class RedisJobStore:
    """Redis adapter for the same job contract; dependency is optional and lazy."""
    def __init__(self, client, prefix: str = "archai"):
        self.client, self.prefix = client, prefix

    @classmethod
    def from_url(cls, url: str, prefix: str = "archai") -> "RedisJobStore":
        try:
            import redis
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("install the platform extra to use RedisJobStore") from exc
        return cls(redis.Redis.from_url(url, decode_responses=True), prefix)

    def _key(self, job_id: str) -> str:
        return f"{self.prefix}:job:{job_id}"

    def create(self, kind: str, payload: dict | None = None) -> Job:
        job = Job(uuid4().hex, kind, payload=payload or {})
        self.client.set(self._key(job.job_id), json.dumps(job.as_dict()))
        self.client.rpush(f"{self.prefix}:queue", job.job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        value = self.client.get(self._key(job_id))
        return Job.from_dict(json.loads(value)) if value else None

    def transition(self, job_id: str, status: JobStatus, error: str | None = None) -> Job:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if status not in _TRANSITIONS[job.status]:
            raise ValueError(f"invalid job transition {job.status}->{status}")
        job.status, job.error, job.updated_at = status, error, datetime.now(timezone.utc)
        self.client.set(self._key(job_id), json.dumps(job.as_dict()))
        return job

    def pop_queued(self, timeout: int = 0) -> Job | None:
        value = self.client.blpop(f"{self.prefix}:queue", timeout=timeout)
        if not value:
            return None
        job_id = value[1] if isinstance(value, tuple) else value
        return self.transition(job_id, "running")

    def list(self) -> list[Job]:
        jobs = []
        for key in self.client.scan_iter(match=f"{self.prefix}:job:*"):
            value = self.client.get(key)
            if value:
                jobs.append(Job.from_dict(json.loads(value)))
        return jobs
