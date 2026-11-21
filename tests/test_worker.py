import hashlib
import json

import pytest

from archai_shared.jobs import InMemoryJobStore
from archai_shared.worker import WorkerRunner, run_job


def test_worker_captures_success_and_failure():
    store = InMemoryJobStore()
    success = store.create("training")
    assert run_job(store, success.job_id, lambda job: {"loss": 0.2}).status == "succeeded"
    assert store.get(success.job_id).payload["result"] == {"loss": 0.2}
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


def test_worker_cancellation_during_handler_stays_terminal():
    store = InMemoryJobStore()
    job = store.create("training")

    def cancel_inside_handler(current_job):
        store.transition(current_job.job_id, "cancelled")
        return {"should_not": "persist"}

    result = WorkerRunner(store, {"training": cancel_inside_handler}).run_once()
    assert result.status == "cancelled"
    assert "result" not in store.get(job.job_id).payload

    direct = store.create("training")

    def cancel_direct(current_job):
        store.transition(current_job.job_id, "cancelled")
        return {"ignored": True}

    assert run_job(store, direct.job_id, cancel_direct).status == "cancelled"


def test_benchmark_handler_requires_verified_archive_configuration(monkeypatch):
    from archai_api.worker import benchmark_search

    monkeypatch.delenv("ARCHAI_NATS_BENCH_PATH", raising=False)
    monkeypatch.delenv("ARCHAI_NATS_BENCH_SHA256", raising=False)
    job = InMemoryJobStore().create("search", {"budget_evaluations": 1})
    with pytest.raises(RuntimeError, match="ARCHAI_NATS_BENCH_PATH"):
        benchmark_search(job)


def test_training_handler_compiles_and_trains_explicit_synthetic_candidate(tmp_path):
    pytest.importorskip("torch")
    from archai_api.worker import candidate_training
    from archai_core.schema import Architecture, Edge, Node, TensorSpec

    architecture = Architecture(nodes=[Node(id="input", op="input", channels=3),
                                       Node(id="conv", op="conv3x3", channels=4),
                                       Node(id="output", op="output", channels=4)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=4, width=4), output_classes=2)
    job = InMemoryJobStore().create("training", {"architecture": architecture.model_dump(),
        "dataset": "synthetic", "train_samples": 4, "validation_samples": 4,
        "batch_size": 2, "epochs": 1, "seed": 7,
        "checkpoint_path": str(tmp_path / "candidate.pt")})
    result = candidate_training(job)
    assert result["status"] == "completed"
    assert result["evidence_type"] == "synthetic_training"
    assert "python=" in result["hardware"]
    assert result["checkpoint_sha256"] == hashlib.sha256((tmp_path / "candidate.pt").read_bytes()).hexdigest()
    assert (tmp_path / "candidate.pt").exists()


def test_training_handler_rejects_implicit_real_dataset_substitution():
    from archai_api.worker import candidate_training

    job = InMemoryJobStore().create("training", {"dataset": "cifar10"})
    with pytest.raises(RuntimeError, match="dataset=synthetic"):
        candidate_training(job)


def test_generator_training_handler_writes_checkpoint(tmp_path):
    pytest.importorskip("torch")
    from archai_api.worker import generator_training
    from archai_core.schema import Architecture, Edge, Node, TensorSpec

    architecture = Architecture(nodes=[Node(id="input", op="input", channels=3),
                                       Node(id="conv", op="conv3x3", channels=4),
                                       Node(id="output", op="output", channels=4)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=4, width=4), output_classes=2)
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"architecture": architecture.model_dump(), "condition": [0.0] * 8}) + "\n")
    checkpoint = tmp_path / "generator.pt"
    job = InMemoryJobStore().create("generator_training", {"corpus_path": str(corpus),
        "checkpoint_path": str(checkpoint), "epochs": 1, "seed": 3, "sample_count": 2})
    result = generator_training(job)
    assert result["status"] == "completed"
    assert result["evidence_type"] == "generator_training"
    assert "torch=" in result["hardware"]
    assert result["checkpoint_sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert checkpoint.exists()


def test_predictor_training_handler_requires_verified_archive_configuration():
    from archai_api.worker import predictor_training

    job = InMemoryJobStore().create("predictor_training", {"indices": [1, 2, 3]})
    with pytest.raises(RuntimeError, match="benchmark_path"):
        predictor_training(job)


def test_benchmark_handler_does_not_mislabel_unsupported_algorithm(monkeypatch):
    from archai_api.worker import benchmark_search

    monkeypatch.setenv("ARCHAI_NATS_BENCH_PATH", "/tmp/archive")
    monkeypatch.setenv("ARCHAI_NATS_BENCH_SHA256", "a" * 64)
    job = InMemoryJobStore().create("search", {"algorithm": "bayesian", "budget_evaluations": 1})
    with pytest.raises(RuntimeError, match="random or evolution"):
        benchmark_search(job)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.queue = []

    def ping(self):
        return True

    def set(self, key, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def rpush(self, _key, value):
        self.queue.append(value)

    def blpop(self, _key, timeout=0):
        return ("archai:queue", self.queue.pop(0)) if self.queue else None

    def scan_iter(self, match=None):
        return iter(self.values)


def test_redis_worker_round_trip_persists_result():
    from archai_shared.jobs import RedisJobStore

    store = RedisJobStore(FakeRedis())
    job = store.create("training", {"seed": 4})
    runner = WorkerRunner(store, {"training": lambda _job: {"accuracy": 0.9}})
    result = runner.run_once()
    assert result.status == "succeeded"
    assert store.get(job.job_id).payload["result"] == {"accuracy": 0.9}
