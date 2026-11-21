from __future__ import annotations

from threading import Event
from typing import Protocol

from .jobs import InMemoryJobStore, Job, RedisJobStore

JobStore = InMemoryJobStore | RedisJobStore


class JobHandler(Protocol):
    def __call__(self, job: Job) -> None: ...


def run_job(store: JobStore, job_id: str, handler: JobHandler) -> Job:
    """Execute one claimed job with terminal failure capture."""
    job = store.transition(job_id, "running")
    try:
        handler(job)
    except Exception as exc:
        return store.transition(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
    return store.transition(job_id, "succeeded")


class WorkerRunner:
    """Execute queued jobs from either the local or Redis job adapter.

    Handlers are explicitly registered by job kind. A missing handler is a
    terminal failure, which keeps unsupported work visible to operators.
    """

    def __init__(self, store: JobStore, handlers: dict[str, JobHandler]):
        self.store = store
        self.handlers = handlers

    def claim(self, timeout: int = 0) -> Job | None:
        if isinstance(self.store, RedisJobStore):
            try:
                return self.store.pop_queued(timeout=timeout)
            except ValueError:
                # A queued Redis entry can outlive a cancellation request.
                return None
        return self.store.pop_queued()

    def run_once(self, timeout: int = 0) -> Job | None:
        job = self.claim(timeout=timeout)
        if job is None:
            return None
        handler = self.handlers.get(job.kind)
        if handler is None:
            return self.store.transition(job.job_id, "failed", error=f"no handler registered for job kind: {job.kind}")
        try:
            handler(job)
        except Exception as exc:
            return self.store.transition(job.job_id, "failed", error=f"{type(exc).__name__}: {exc}")
        return self.store.transition(job.job_id, "succeeded")

    def run_forever(self, *, stop: Event | None = None, timeout: int = 5) -> None:
        stop = stop or Event()
        while not stop.is_set():
            self.run_once(timeout=timeout)
