import pytest

from archai_shared.jobs import InMemoryJobStore
from archai_shared.worker import WorkerRunner, run_job


def test_worker_captures_success_and_failure():
    store = InMemoryJobStore()
    success = store.create("training")
    assert run_job(store, success.job_id, lambda job: None).status == "succeeded"
    failure = store.create("training")
    result = run_job(store, failure.job_id, lambda job: (_ for _ in ()).throw(RuntimeError("boom")))
    assert result.status == "failed"
    assert "boom" in result.error


def test_worker_runner_claims_jobs_and_records_missing_handlers():
    store = InMemoryJobStore()
    seen = []
    handled = store.create("training", {"value": 4})
    runner = WorkerRunner(store, {"training": lambda job: (seen.append(job.payload["value"]) or {"loss": 0.25})})
    assert runner.run_once().status == "succeeded"
    assert seen == [4]
    assert store.get(handled.job_id).payload["result"] == {"loss": 0.25}

    unsupported = store.create("search")
    result = runner.run_once()
    assert result.job_id == unsupported.job_id
    assert result.status == "failed"
    assert "no handler registered" in result.error


def test_benchmark_handler_requires_verified_archive_configuration(monkeypatch):
    from archai_api.worker import benchmark_search

    monkeypatch.delenv("ARCHAI_NATS_BENCH_PATH", raising=False)
    monkeypatch.delenv("ARCHAI_NATS_BENCH_SHA256", raising=False)
    job = InMemoryJobStore().create("search", {"budget_evaluations": 1})
    with pytest.raises(RuntimeError, match="ARCHAI_NATS_BENCH_PATH"):
        benchmark_search(job)
