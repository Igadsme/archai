from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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

    def update_payload(self, job_id: str, payload: dict) -> Job:
        with self._lock:
            job = self._jobs[job_id]
            job.payload = dict(payload)
            job.updated_at = datetime.now(timezone.utc)
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

    def _worker_key(self, worker_id: str) -> str:
        return f"{self.prefix}:worker:{worker_id}"

    def create(self, kind: str, payload: dict | None = None) -> Job:
        job = Job(uuid4().hex, kind, payload=payload or {})
        serialized = json.dumps(job.as_dict())
        if hasattr(self.client, "pipeline"):
            pipe = self.client.pipeline(transaction=True)
            pipe.set(self._key(job.job_id), serialized)
            pipe.rpush(f"{self.prefix}:queue", job.job_id)
            pipe.execute()
        else:
            self.client.set(self._key(job.job_id), serialized)
            self.client.rpush(f"{self.prefix}:queue", job.job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        value = self.client.get(self._key(job_id))
        return Job.from_dict(json.loads(value)) if value else None

    def transition(self, job_id: str, status: JobStatus, error: str | None = None) -> Job:
        def update(job: Job) -> Job:
            if status not in _TRANSITIONS[job.status]:
                raise ValueError(f"invalid job transition {job.status}->{status}")
            job.status, job.error, job.updated_at = status, error, datetime.now(timezone.utc)
            return job

        return self._atomic_job_update(job_id, update)

    def update_payload(self, job_id: str, payload: dict) -> Job:
        def update(job: Job) -> Job:
            job.payload = dict(payload)
            job.updated_at = datetime.now(timezone.utc)
            return job

        return self._atomic_job_update(job_id, update)

    def _atomic_job_update(self, job_id: str, updater) -> Job:
        """CAS-update a job when Redis transactions are available."""
        key = self._key(job_id)
        if not hasattr(self.client, "pipeline"):
            job = self.get(job_id)
            if job is None:
                raise KeyError(job_id)
            job = updater(job)
            self.client.set(key, json.dumps(job.as_dict()))
            return job
        try:
            from redis.exceptions import WatchError
        except ImportError:  # pragma: no cover - only reached with a custom Redis client
            WatchError = RuntimeError
        while True:
            pipe = self.client.pipeline(transaction=True)
            try:
                pipe.watch(key)
                raw = pipe.get(key)
                if not raw:
                    raise KeyError(job_id)
                job = updater(Job.from_dict(json.loads(raw)))
                pipe.multi()
                pipe.set(key, json.dumps(job.as_dict()))
                pipe.execute()
                return job
            except WatchError:
                continue
            finally:
                pipe.reset()

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

    def heartbeat(self, worker_id: str, *, active_job_id: str | None = None) -> dict:
        """Record a worker liveness signal and the job currently being handled."""
        value = {
            "worker_id": worker_id,
            "hostname": socket.gethostname(),
            "pid": __import__("os").getpid(),
            "status": "running" if active_job_id else "idle",
            "active_job_id": active_job_id,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        self.client.set(self._worker_key(worker_id), json.dumps(value))
        return value

    def list_workers(self, *, stale_after_seconds: float = 30.0) -> list[dict]:
        """Return workers whose latest heartbeat is recent enough to be live."""
        now = datetime.now(timezone.utc)
        workers = []
        for key in self.client.scan_iter(match=f"{self.prefix}:worker:*"):
            value = self.client.get(key)
            if not value:
                continue
            try:
                worker = json.loads(value)
                last_seen = datetime.fromisoformat(worker["last_seen"])
                if (now - last_seen).total_seconds() <= stale_after_seconds:
                    workers.append(worker)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return sorted(workers, key=lambda item: item.get("worker_id", ""))

    def recover_stale_jobs(self, *, stale_after_seconds: float = 60.0) -> list[str]:
        """Requeue running jobs whose worker lease has expired."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        active_jobs = {worker.get("active_job_id") for worker in self.list_workers()}
        recovered = []
        for key in self.client.scan_iter(match=f"{self.prefix}:job:*"):
            value = self.client.get(key)
            if not value:
                continue
            try:
                job = Job.from_dict(json.loads(value))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if job.status != "running" or job.job_id in active_jobs or job.updated_at > cutoff:
                continue

            def requeue(current: Job) -> Job:
                if current.status != "running":
                    raise ValueError("job is no longer running")
                current.status = "queued"
                current.error = "requeued after worker lease expired"
                current.updated_at = datetime.now(timezone.utc)
                return current

            try:
                self._atomic_job_update(job.job_id, requeue)
            except (KeyError, ValueError):
                continue
            self.client.rpush(f"{self.prefix}:queue", job.job_id)
            recovered.append(job.job_id)
        return recovered
