import hashlib
import json
import time
from datetime import UTC, datetime, timedelta

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


def test_training_handler_defaults_checkpoints_to_the_configured_directory(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    from archai_api.worker import candidate_training
    from archai_core.schema import Architecture, Edge, Node, TensorSpec

    monkeypatch.setenv("ARCHAI_CHECKPOINT_DIR", str(tmp_path / "checkpoints"))
    architecture = Architecture(nodes=[Node(id="input", op="input", channels=3),
                                       Node(id="conv", op="conv3x3", channels=4),
                                       Node(id="output", op="output", channels=4)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=4, width=4), output_classes=2)
    job = InMemoryJobStore().create("training", {"architecture": architecture.model_dump(),
        "dataset": "synthetic", "train_samples": 4, "validation_samples": 4, "batch_size": 2, "epochs": 1})
    result = candidate_training(job)
    expected = tmp_path / "checkpoints" / f"candidate-{job.job_id}.pt"
    assert result["checkpoint_path"] == str(expected) and expected.exists()


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
    job = InMemoryJobStore().create("search", {"algorithm": "reinforcement", "budget_evaluations": 1})
    with pytest.raises(RuntimeError, match="supports algorithm=random, evolution, reinforce"):
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


class TransactionalFakeRedis(FakeRedis):
    class Pipeline:
        def __init__(self, parent):
            self.parent = parent
            self.commands = []

        def watch(self, _key):
            return None

        def get(self, key):
            return self.parent.get(key)

        def multi(self):
            return None

        def set(self, key, value):
            self.commands.append(("set", key, value))

        def rpush(self, key, value):
            self.commands.append(("rpush", key, value))

        def execute(self):
            for command, key, value in self.commands:
                getattr(self.parent, command)(key, value)
            self.commands = []
            return []

        def reset(self):
            self.commands = []

    def pipeline(self, transaction=True):
        return self.Pipeline(self)


def test_redis_worker_round_trip_persists_result():
    from archai_shared.jobs import RedisJobStore

    store = RedisJobStore(FakeRedis())
    job = store.create("training", {"seed": 4})
    runner = WorkerRunner(store, {"training": lambda _job: {"accuracy": 0.9}})
    result = runner.run_once()
    assert result.status == "succeeded"
    assert store.get(job.job_id).payload["result"] == {"accuracy": 0.9}


def test_redis_store_uses_transactional_job_writes():
    from archai_shared.jobs import RedisJobStore

    store = RedisJobStore(TransactionalFakeRedis())
    job = store.create("training", {"seed": 2})
    assert store.transition(job.job_id, "cancelled").status == "cancelled"
    assert store.get(job.job_id).status == "cancelled"


def test_redis_store_recovers_only_jobs_without_live_worker_lease():
    from archai_shared.jobs import RedisJobStore

    client = FakeRedis()
    store = RedisJobStore(client)
    stale = store.create("training")
    store.transition(stale.job_id, "running")
    raw = json.loads(client.values[store._key(stale.job_id)])
    raw["updated_at"] = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    client.values[store._key(stale.job_id)] = json.dumps(raw)
    assert store.recover_stale_jobs(stale_after_seconds=30) == [stale.job_id]
    assert store.get(stale.job_id).status == "queued"
    assert client.queue[-1] == stale.job_id

    protected = store.create("training")
    store.transition(protected.job_id, "running")
    raw = json.loads(client.values[store._key(protected.job_id)])
    raw["updated_at"] = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    client.values[store._key(protected.job_id)] = json.dumps(raw)
    store.heartbeat("worker-live", active_job_id=protected.job_id)
    assert store.recover_stale_jobs(stale_after_seconds=30) == []
    assert store.get(protected.job_id).status == "running"


def test_redis_worker_heartbeat_reports_idle_and_active_state():
    from archai_shared.jobs import RedisJobStore

    client = FakeRedis()
    store = RedisJobStore(client)
    store.heartbeat("worker-a")
    idle = store.list_workers()
    assert idle[0]["worker_id"] == "worker-a"
    assert idle[0]["status"] == "idle"

    store.heartbeat("worker-a", active_job_id="job-1")
    active = store.list_workers()
    assert active[0]["status"] == "running"
    assert active[0]["active_job_id"] == "job-1"


def test_worker_runner_emits_redis_heartbeats():
    from archai_shared.jobs import RedisJobStore

    store = RedisJobStore(FakeRedis())
    store.create("training")
    runner = WorkerRunner(store, {"training": lambda _job: {"ok": True}}, worker_id="worker-test")
    assert runner.run_once().status == "succeeded"
    worker = store.list_workers()[0]
    assert worker["worker_id"] == "worker-test"
    assert worker["status"] == "idle"
    assert datetime.fromisoformat(worker["last_seen"]).tzinfo == UTC


def test_worker_runner_refreshes_heartbeat_during_long_handler():
    from archai_shared.jobs import RedisJobStore

    store = RedisJobStore(FakeRedis())
    job = store.create("training")
    observed = []

    def slow_handler(_job):
        time.sleep(0.03)
        observed.extend(store.list_workers())
        return None

    runner = WorkerRunner(store, {"training": slow_handler}, worker_id="worker-long", heartbeat_interval=0.005)
    assert runner.run_once().status == "succeeded"
    assert observed and observed[0]["status"] == "running"
    assert observed[0]["active_job_id"] == job.job_id


def test_benchmark_worker_runs_bayesian_search_on_verified_directory(monkeypatch, tmp_path):
    import archai_benchmark
    from archai_api.worker import benchmark_search
    from archai_benchmark.adapter import BenchmarkRecord
    from archai_benchmark.integrity import sha256_tree

    ops = ("none", "skip_connect", "nor_conv_1x1", "nor_conv_3x3", "avg_pool_3x3")

    class FakeAdapter:
        dataset = "cifar10"

        def __init__(self, *_args):
            pass

        def open(self):
            return self

        def architecture_string(self, index):
            o = [ops[(index // 5 ** p) % 5] for p in range(6)]
            return f"|{o[0]}~0|+|{o[1]}~0|{o[2]}~1|+|{o[3]}~0|{o[4]}~1|{o[5]}~2|"

        def query(self, index, seed=0):
            return BenchmarkRecord(index, "cifar10", seed, 80.0 + index % 7, 79.0, 1.0,
                                   architecture_string=self.architecture_string(index))

    archive = tmp_path / "NATS-simple"
    archive.mkdir()
    (archive / "meta.pickle.pbz2").write_bytes(b"meta")
    monkeypatch.setattr(archai_benchmark, "NATSBenchAdapter", FakeAdapter)
    monkeypatch.setenv("ARCHAI_NATS_BENCH_PATH", str(archive))
    monkeypatch.setenv("ARCHAI_NATS_BENCH_SHA256", sha256_tree(archive))
    monkeypatch.setenv("ARCHAI_BENCHMARK_CACHE", str(tmp_path / "cache.sqlite"))
    payload = {"algorithm": "bayesian", "budget_evaluations": 6, "seed": 1,
               "indices": list(range(30)), "warmup": 2}
    first = benchmark_search(InMemoryJobStore().create("search", payload))
    assert (first["evaluations"], first["queries"], first["cache_hits"]) == (6, 6, 0)
    assert first["selected_architecture_string"].startswith("|")
    second = benchmark_search(InMemoryJobStore().create("search", payload))
    assert (second["evaluations"], second["queries"], second["cache_hits"]) == (6, 0, 6)
    assert second["selected_index"] == first["selected_index"]
