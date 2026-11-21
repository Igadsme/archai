from archai_shared.jobs import InMemoryJobStore
from archai_shared.worker import run_job


def test_worker_captures_success_and_failure():
    store = InMemoryJobStore()
    success = store.create("training")
    assert run_job(store, success.job_id, lambda job: None).status == "succeeded"
    failure = store.create("training")
    result = run_job(store, failure.job_id, lambda job: (_ for _ in ()).throw(RuntimeError("boom")))
    assert result.status == "failed"
    assert "boom" in result.error
