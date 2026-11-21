from __future__ import annotations

import socket
from threading import Event, Thread
from typing import Protocol
from uuid import uuid4

from .jobs import InMemoryJobStore, Job, RedisJobStore

JobStore = InMemoryJobStore | RedisJobStore


class JobHandler(Protocol):
    def __call__(self, job: Job) -> dict | None: ...


def run_job(store: JobStore, job_id: str, handler: JobHandler) -> Job:
    """Execute one claimed job with terminal failure capture."""
    job = store.transition(job_id, "running")
    try:
        result = handler(job)
        latest = store.get(job_id)
        if latest is not None and latest.status == "cancelled":
            return latest
        if result is not None:
            store.update_payload(job_id, {**job.payload, "result": result})
    except Exception as exc:
        latest = store.get(job_id)
        if latest is not None and latest.status == "cancelled":
            return latest
        return store.transition(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
    return store.transition(job_id, "succeeded")


class WorkerRunner:
    """Execute queued jobs from either the local or Redis job adapter.

    Handlers are explicitly registered by job kind. A missing handler is a
    terminal failure, which keeps unsupported work visible to operators.
    """

    def __init__(self, store: JobStore, handlers: dict[str, JobHandler], *, worker_id: str | None = None,
                 heartbeat_interval: float = 5.0):
        self.store = store
        self.handlers = handlers
        self.worker_id = worker_id or f"{socket.gethostname()}-{uuid4().hex[:12]}"
        if heartbeat_interval <= 0:
            raise ValueError("heartbeat_interval must be positive")
        self.heartbeat_interval = heartbeat_interval

    def _heartbeat(self, active_job_id: str | None = None) -> None:
        if isinstance(self.store, RedisJobStore):
            try:
                self.store.heartbeat(self.worker_id, active_job_id=active_job_id)
            except Exception:
                # Liveness reporting must not turn a successful job into a failure.
                pass

    def _heartbeat_loop(self, active_job_id: str, stop: Event) -> None:
        while not stop.wait(self.heartbeat_interval):
            self._heartbeat(active_job_id)

    def claim(self, timeout: int = 0) -> Job | None:
        if isinstance(self.store, RedisJobStore):
            try:
                return self.store.pop_queued(timeout=timeout)
            except ValueError:
                # A queued Redis entry can outlive a cancellation request.
                return None
        return self.store.pop_queued()

    def run_once(self, timeout: int = 0) -> Job | None:
        self._heartbeat()
        job = self.claim(timeout=timeout)
        if job is None:
            return None
        self._heartbeat(job.job_id)
        heartbeat_stop = Event()
        heartbeat_thread = Thread(target=self._heartbeat_loop, args=(job.job_id, heartbeat_stop), daemon=True)
        heartbeat_thread.start()
        try:
            handler = self.handlers.get(job.kind)
            if handler is None:
                return self.store.transition(job.job_id, "failed", error=f"no handler registered for job kind: {job.kind}")
            result = handler(job)
            latest = self.store.get(job.job_id)
            if latest is not None and latest.status == "cancelled":
                return latest
            if result is not None:
                self.store.update_payload(job.job_id, {**job.payload, "result": result})
        except Exception as exc:
            latest = self.store.get(job.job_id)
            if latest is not None and latest.status == "cancelled":
                return latest
            return self.store.transition(job.job_id, "failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=max(1.0, self.heartbeat_interval))
            self._heartbeat()
        return self.store.transition(job.job_id, "succeeded")

    def run_forever(self, *, stop: Event | None = None, timeout: int = 5) -> None:
        stop = stop or Event()
        while not stop.is_set():
            if isinstance(self.store, RedisJobStore):
                self.store.recover_stale_jobs()
            self.run_once(timeout=timeout)
