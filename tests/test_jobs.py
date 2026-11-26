import pytest
from archai_shared.jobs import InMemoryJobStore


def test_job_transitions_are_idempotency_safe():
    store = InMemoryJobStore()
    job = store.create("search")
    assert store.transition(job.job_id, "running").status == "running"
    assert store.transition(job.job_id, "cancelled").status == "cancelled"
    with pytest.raises(ValueError, match="invalid job transition"):
        store.transition(job.job_id, "succeeded")
