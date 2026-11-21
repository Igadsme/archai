"""Durable worker entry point for the API job queue."""
from __future__ import annotations

import os
from pathlib import Path

from archai_shared.jobs import RedisJobStore
from archai_shared.jobs import Job
from archai_shared.worker import WorkerRunner


def candidate_training(job: Job) -> dict:
    """Compile and train one candidate from an explicit worker payload.

    The durable worker currently supports only an in-memory synthetic dataset.
    This is intentional: real datasets must be acquired and registered before
    a handler is allowed to claim them, so a missing dataset can never be
    silently replaced by synthetic data.
    """
    config = job.payload
    if config.get("dataset", "synthetic") != "synthetic":
        raise RuntimeError("training worker currently supports dataset=synthetic only")
    architecture_payload = config.get("architecture")
    if not isinstance(architecture_payload, dict):
        raise RuntimeError("training jobs require an architecture object")
    try:
        import torch
        from torch.utils.data import DataLoader, TensorDataset
        from archai_core.schema import Architecture
        from archai_training.candidate import train_candidate
        from archai_training.engine import TrainingConfig
    except ImportError as exc:
        raise RuntimeError("install the ml extra for training workers") from exc

    architecture = Architecture.model_validate(architecture_payload)
    seed = int(config.get("seed", 0))
    train_samples = int(config.get("train_samples", 16))
    validation_samples = int(config.get("validation_samples", 8))
    batch_size = int(config.get("batch_size", 4))
    if min(train_samples, validation_samples, batch_size) <= 0:
        raise RuntimeError("training sample counts and batch_size must be positive")
    shape = (architecture.input_spec.channels, architecture.input_spec.height,
             architecture.input_spec.width)
    generator = torch.Generator().manual_seed(seed)
    train_inputs = torch.randn((train_samples, *shape), generator=generator)
    train_targets = torch.randint(0, architecture.output_classes, (train_samples,), generator=generator)
    validation_inputs = torch.randn((validation_samples, *shape), generator=generator)
    validation_targets = torch.randint(0, architecture.output_classes, (validation_samples,), generator=generator)
    train_loader = DataLoader(TensorDataset(train_inputs, train_targets), batch_size=batch_size, shuffle=True,
                              generator=torch.Generator().manual_seed(seed))
    validation_loader = DataLoader(TensorDataset(validation_inputs, validation_targets), batch_size=batch_size)
    training_config = TrainingConfig(
        epochs=int(config.get("epochs", 1)),
        learning_rate=float(config.get("learning_rate", 1e-3)),
        weight_decay=float(config.get("weight_decay", 0.0)),
        gradient_accumulation_steps=int(config.get("gradient_accumulation_steps", 1)),
        early_stopping_patience=int(config.get("early_stopping_patience", 0)),
        mixed_precision=bool(config.get("mixed_precision", False)),
        seed=seed,
        device=str(config.get("device", "cpu")),
    )
    checkpoint = config.get("checkpoint_path")
    result = train_candidate(architecture, train_loader, validation_loader, training_config,
                             checkpoint_path=checkpoint)
    return {"status": result.status, "architecture_id": architecture.content_hash(),
            "best_validation_loss": result.best_validation_loss,
            "epochs_completed": result.epochs_completed,
            "wall_clock_seconds": result.wall_clock_seconds,
            "history": list(result.history), "checkpoint_path": result.checkpoint_path,
            "evidence_type": "synthetic_training", "seed": seed}


def benchmark_search(job: Job) -> dict:
    """Run the configured validation-selected benchmark search.

    The archive checksum is mandatory so a worker cannot silently query an
    unverified or stale benchmark file.
    """
    algorithm = job.payload.get("algorithm", "random")
    if algorithm not in {"random", "evolution"}:
        raise RuntimeError("benchmark worker supports algorithm=random or evolution")
    try:
        from archai_benchmark import (BenchmarkCache, BenchmarkEvaluator, IndexRandomSearch,
                                      IndexRegularizedEvolution, NATSBenchAdapter, QueryBudget)
        from archai_benchmark.integrity import sha256_file
    except ImportError as exc:
        raise RuntimeError("install the benchmark extra for benchmark search workers") from exc
    path = os.getenv("ARCHAI_NATS_BENCH_PATH")
    expected_checksum = os.getenv("ARCHAI_NATS_BENCH_SHA256")
    if not path or not expected_checksum:
        raise RuntimeError("ARCHAI_NATS_BENCH_PATH and ARCHAI_NATS_BENCH_SHA256 are required")
    archive = Path(path)
    if not archive.is_file():
        raise RuntimeError(f"benchmark archive is unavailable: {archive}")
    actual_checksum = sha256_file(archive)
    if actual_checksum != expected_checksum.lower():
        raise RuntimeError("benchmark archive checksum mismatch")
    config = job.payload
    raw_indices = config.get("indices") or [int(value) for value in os.getenv("ARCHAI_NATS_BENCH_INDICES", "").split(",") if value.strip()]
    indices = [int(value) for value in raw_indices]
    if not indices:
        raise RuntimeError("no benchmark indices configured")
    budget = min(int(config["budget_evaluations"]), len(indices))
    dataset = str(config.get("dataset_id", "cifar10"))
    search_space = os.getenv("ARCHAI_NATS_BENCH_SEARCH_SPACE", "tss")
    cache_path = os.getenv("ARCHAI_BENCHMARK_CACHE", "/tmp/archai-benchmark-cache.sqlite")
    adapter = NATSBenchAdapter(str(archive), search_space, dataset).open()
    evaluator = BenchmarkEvaluator(adapter, QueryBudget(budget), BenchmarkCache(cache_path))
    if algorithm == "random":
        policy = IndexRandomSearch(indices, seed=int(config.get("seed", 0)))
    else:
        architecture_strings = {index: adapter.architecture_string(index) for index in indices}
        policy = IndexRegularizedEvolution(
            indices, architecture_strings,
            population_size=int(config.get("population_size", 8)),
            sample_size=int(config.get("sample_size", 3)),
            seed=int(config.get("seed", 0)),
        )
    records = []
    while len(records) < budget:
        index = policy.ask()
        if index is None:
            break
        record = evaluator.evaluate_index(index, seed=int(config.get("seed", 0)))
        records.append(record)
        if algorithm == "evolution":
            policy.tell(index, record.validation_accuracy)
    if not records:
        raise RuntimeError("benchmark search evaluated no architectures")
    best = max(records, key=lambda record: record.validation_accuracy)
    return {"algorithm": algorithm, "dataset": dataset, "search_space": search_space,
            "seed": int(config.get("seed", 0)), "budget": int(config["budget_evaluations"]),
            "queries": evaluator.queries, "selected_on": "validation_accuracy",
            "selected_index": best.architecture_index,
            "selected_validation_accuracy": best.validation_accuracy,
            "held_out_test_accuracy": best.test_accuracy,
            "evidence_type": "benchmark_lookup",
            "evaluated_indices": [record.architecture_index for record in records],
            "archive_sha256": actual_checksum}


def main() -> int:
    url = os.getenv("ARCHAI_REDIS_URL")
    if not url:
        raise SystemExit("ARCHAI_REDIS_URL is required for the durable worker")
    store = RedisJobStore.from_url(url)
    store.client.ping()
    WorkerRunner(store, {"search": benchmark_search, "training": candidate_training}).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
