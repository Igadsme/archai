from __future__ import annotations

import logging
import socket
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from threading import Event, Thread
from typing import Protocol
from uuid import uuid4

from .jobs import InMemoryJobStore, Job, RedisJobStore

JobStore = InMemoryJobStore | RedisJobStore
_log = logging.getLogger("archai.worker")


class JobHandler(Protocol):
    def __call__(self, job: Job) -> dict | None: ...


class JobCancelled(RuntimeError):
    """Raised inside a handler when an operator cancelled the job it is running."""


class JobContext:
    """Progress and cancellation channel for the job a handler is currently executing.

    Progress writes are throttled so a long search cannot flood the job store; the
    final call for a phase should pass `force=True`.
    """

    def __init__(self, store: JobStore, job_id: str, *, min_interval: float = 1.0,
                 clock=time.monotonic):
        self.store, self.job_id, self.min_interval, self.clock = store, job_id, min_interval, clock
        self._last_report: float | None = None
        self._last_cancel_check: float | None = None

    def report(self, progress: dict, *, force: bool = False) -> bool:
        now = self.clock()
        if not force and self._last_report is not None and now - self._last_report < self.min_interval:
            return False
        self._last_report = now
        try:
            self.store.update_progress(self.job_id, {**progress, "reported_at": datetime.now(UTC).isoformat()})
        except Exception:  # progress is advisory; it must never fail the job
            _log.warning("could not record progress for job %s", self.job_id, exc_info=True)
            return False
        return True

    def cancelled(self) -> bool:
        try:
            latest = self.store.get(self.job_id)
        except Exception:
            return False
        return latest is not None and latest.status == "cancelled"

    def raise_if_cancelled(self, *, force: bool = False) -> None:
        now = self.clock()
        if not force and self._last_cancel_check is not None and now - self._last_cancel_check < self.min_interval:
            return
        self._last_cancel_check = now
        if self.cancelled():
            raise JobCancelled(f"job {self.job_id} was cancelled")


_current_context: ContextVar[JobContext | None] = ContextVar("archai_job_context", default=None)


@contextmanager
def job_context(store: JobStore, job_id: str):
    token = _current_context.set(JobContext(store, job_id))
    try:
        yield _current_context.get()
    finally:
        _current_context.reset(token)


def report_progress(progress: dict, *, force: bool = False) -> None:
    """Record progress for the running job; a no-op outside a worker (e.g. CLI or tests)."""
    context = _current_context.get()
    if context is not None:
        context.report(progress, force=force)


def raise_if_cancelled(*, force: bool = False) -> None:
    context = _current_context.get()
    if context is not None:
        context.raise_if_cancelled(force=force)


def _result_payload(store: JobStore, job: Job, result: dict) -> dict:
    latest = store.get(job.job_id)
    return {**(latest.payload if latest is not None else job.payload), "result": result}


def run_job(store: JobStore, job_id: str, handler: JobHandler) -> Job:
    """Execute one claimed job with terminal failure capture."""
    job = store.transition(job_id, "running")
    try:
        with job_context(store, job_id):
            result = handler(job)
        latest = store.get(job_id)
        if latest is not None and latest.status == "cancelled":
            return latest
        if result is not None:
            store.update_payload(job_id, _result_payload(store, job, result))
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
            with job_context(self.store, job.job_id):
                result = handler(job)
            latest = self.store.get(job.job_id)
            if latest is not None and latest.status == "cancelled":
                return latest
            if result is not None:
                self.store.update_payload(job.job_id, _result_payload(self.store, job, result))
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
