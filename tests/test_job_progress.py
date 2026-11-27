import pytest
from archai_shared.jobs import InMemoryJobStore, RedisJobStore
from archai_shared.worker import (
    JobCancelled,
    JobContext,
    WorkerRunner,
    raise_if_cancelled,
    report_progress,
    run_job,
)

from tests.test_worker import TransactionalFakeRedis


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def tiny_architecture():
    from archai_core.schema import Architecture, Edge, Node, TensorSpec
    return Architecture(nodes=[Node(id="input", op="input", channels=3),
                               Node(id="conv", op="conv3x3", channels=4),
                               Node(id="output", op="output", channels=4)],
                        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
                        input_spec=TensorSpec(channels=3, height=4, width=4), output_classes=2)


def test_progress_reports_are_throttled_unless_forced():
    store = InMemoryJobStore()
    job = store.create("search")
    clock = Clock()
    context = JobContext(store, job.job_id, min_interval=1.0, clock=clock)
    assert context.report({"step": 1})
    assert not context.report({"step": 2})
    assert store.get(job.job_id).payload["progress"]["step"] == 1
    assert context.report({"step": 3}, force=True)
    clock.now = 5.0
    assert context.report({"step": 4})
    progress = store.get(job.job_id).payload["progress"]
    assert progress["step"] == 4 and progress["reported_at"]


def test_progress_and_result_are_both_kept_on_success():
    store = InMemoryJobStore()
    job = store.create("search", {"seed": 1})

    def handler(_job):
        report_progress({"evaluations": 3, "budget": 3}, force=True)
        return {"best": 0.9}

    finished = run_job(store, job.job_id, handler)
    assert finished.status == "succeeded"
    payload = store.get(job.job_id).payload
    assert payload["seed"] == 1
    assert payload["progress"]["evaluations"] == 3
    assert payload["result"] == {"best": 0.9}


def test_progress_helpers_are_no_ops_outside_a_worker():
    report_progress({"step": 1}, force=True)
    raise_if_cancelled(force=True)


def test_cancelled_job_stops_cooperatively_and_stays_cancelled():
    store = InMemoryJobStore()
    job = store.create("search")
    steps = []

    def handler(current):
        for step in range(100):
            if step == 2:
                store.transition(current.job_id, "cancelled")
            raise_if_cancelled(force=True)
            steps.append(step)
        return {"steps": len(steps)}

    finished = WorkerRunner(store, {"search": handler}).run_once()
    assert finished.status == "cancelled"
    assert steps == [0, 1]
    assert "result" not in store.get(job.job_id).payload


def test_job_context_raises_job_cancelled():
    store = InMemoryJobStore()
    job = store.create("search")
    store.transition(job.job_id, "cancelled")
    with pytest.raises(JobCancelled):
        JobContext(store, job.job_id).raise_if_cancelled(force=True)


def test_redis_progress_updates_leave_status_and_payload_intact():
    store = RedisJobStore(TransactionalFakeRedis())
    job = store.create("training", {"seed": 2})
    store.transition(job.job_id, "running")
    store.update_progress(job.job_id, {"epochs_completed": 1})
    latest = store.get(job.job_id)
    assert latest.status == "running"
    assert latest.payload == {"seed": 2, "progress": {"epochs_completed": 1}}


def test_progress_store_failures_never_fail_the_job():
    class BrokenStore(InMemoryJobStore):
        def update_progress(self, job_id, progress):
            raise ConnectionError("redis down")

    store = BrokenStore()
    job = store.create("search")

    def handler(_job):
        report_progress({"step": 1}, force=True)
        return {"ok": True}

    assert run_job(store, job.job_id, handler).status == "succeeded"


def test_engine_calls_on_epoch_end_and_stops_when_it_raises():
    pytest.importorskip("torch")
    import torch
    from archai_training.engine import TrainingConfig, train_model
    from torch.utils.data import DataLoader, TensorDataset

    data = TensorDataset(torch.randn(8, 4), torch.randint(0, 2, (8,)))
    loader = DataLoader(data, batch_size=4)
    rows = []
    result = train_model(torch.nn.Linear(4, 2), loader, loader, TrainingConfig(epochs=3), on_epoch_end=rows.append)
    assert len(rows) == 3 == result.epochs_completed
    assert rows[0].keys() == {"epoch", "train_loss", "validation_loss", "validation_accuracy"}

    def stop_after_first(_row):
        raise JobCancelled("stop")

    with pytest.raises(JobCancelled):
        train_model(torch.nn.Linear(4, 2), loader, loader, TrainingConfig(epochs=5), on_epoch_end=stop_after_first)


def test_candidate_training_reports_live_epochs(tmp_path):
    pytest.importorskip("torch")
    from archai_api.worker import candidate_training

    store = InMemoryJobStore()
    job = store.create("training", {"architecture": tiny_architecture().model_dump(), "dataset": "synthetic",
                                    "train_samples": 4, "validation_samples": 4, "batch_size": 2,
                                    "epochs": 3, "seed": 7})
    finished = WorkerRunner(store, {"training": candidate_training}).run_once()
    assert finished.status == "succeeded"
    payload = store.get(job.job_id).payload
    assert payload["progress"]["epochs_completed"] == 3
    assert payload["progress"]["epochs"] == 3
    assert len(payload["progress"]["history"]) == 3
    assert payload["result"]["epochs_completed"] == 3


def test_cancelling_candidate_training_stops_after_the_current_epoch(monkeypatch):
    pytest.importorskip("torch")
    from archai_api import worker as api_worker

    store = InMemoryJobStore()
    job = store.create("training", {"architecture": tiny_architecture().model_dump(), "dataset": "synthetic",
                                    "train_samples": 4, "validation_samples": 4, "batch_size": 2,
                                    "epochs": 1000, "seed": 7})
    real_report = api_worker.report_progress
    epochs_seen = []

    def report_then_cancel(progress, *, force=False):
        real_report(progress, force=force)
        epochs_seen.append(progress.get("epochs_completed"))
        if progress.get("epochs_completed") == 2:
            store.transition(job.job_id, "cancelled")

    monkeypatch.setattr(api_worker, "report_progress", report_then_cancel)
    finished = WorkerRunner(store, {"training": api_worker.candidate_training}).run_once()
    assert finished.status == "cancelled"
    assert max(epochs_seen) < 1000
    assert "result" not in store.get(job.job_id).payload
