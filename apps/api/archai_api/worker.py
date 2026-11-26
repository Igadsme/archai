"""Durable worker entry point for the API job queue."""
from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path

from archai_shared.jobs import Job, RedisJobStore
from archai_shared.paths import allowed_path
from archai_shared.worker import WorkerRunner


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hardware_profile(device: str = "cpu", torch_version: str | None = None) -> str:
    python_version = platform.python_version()
    torch_label = f", torch={torch_version}" if torch_version else ""
    return f"{platform.system()} {platform.machine()}, python={python_version}, device={device}{torch_label}"


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
        from archai_core.schema import Architecture
        from archai_training.candidate import train_candidate
        from archai_training.engine import TrainingConfig
        from torch.utils.data import DataLoader, TensorDataset
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
    if checkpoint:
        allowed_path(str(checkpoint), field="checkpoint_path")
    result = train_candidate(architecture, train_loader, validation_loader, training_config,
                             checkpoint_path=checkpoint)
    checkpoint_sha256 = _sha256_file(result.checkpoint_path) if result.checkpoint_path else None
    return {"status": result.status, "architecture_id": architecture.content_hash(),
            "best_validation_loss": result.best_validation_loss,
            "epochs_completed": result.epochs_completed,
            "wall_clock_seconds": result.wall_clock_seconds,
            "history": list(result.history), "checkpoint_path": result.checkpoint_path,
            "checkpoint_sha256": checkpoint_sha256,
            "evidence_type": "synthetic_training", "seed": seed,
            "hardware": _hardware_profile(training_config.device, torch.__version__)}


def generator_training(job: Job) -> dict:
    """Train and checkpoint the conditional generator from an explicit JSONL corpus."""
    config = job.payload
    corpus_path = config.get("corpus_path")
    checkpoint_path = config.get("checkpoint_path")
    if not corpus_path or not checkpoint_path:
        raise RuntimeError("generator jobs require corpus_path and checkpoint_path")
    allowed_path(str(checkpoint_path), field="checkpoint_path")
    from pathlib import Path
    corpus = Path(corpus_path)
    allowed_path(str(corpus), field="corpus_path")
    if not corpus.is_file():
        raise RuntimeError(f"generator corpus is unavailable: {corpus}")
    try:
        import torch
        from archai_generator.model import ArchitectureGenerator, GeneratorConfig
        from archai_generator.training import fit_generator, generation_metrics, save_checkpoint

        from scripts.train_generator import load_examples
    except ImportError as exc:
        raise RuntimeError("install the ml extra for generator workers") from exc
    seed = int(config.get("seed", 0))
    examples = load_examples(corpus)
    model = ArchitectureGenerator(GeneratorConfig(condition_dim=8))
    history = fit_generator(model, examples, epochs=int(config.get("epochs", 20)), seed=seed)
    candidates = model.sample(seed=seed, condition=examples[0][1])[:int(config.get("sample_count", 8))]
    metrics = generation_metrics(candidates)
    metadata = {"model": "ArchAI-V1", "kind": "generator", "seed": seed,
                "corpus_examples": len(examples), "conditional": True,
                "test_selection": "not applicable", "evidence_type": "generator_training"}
    save_checkpoint(model, checkpoint_path, metadata)
    checkpoint_sha256 = _sha256_file(checkpoint_path)
    return {"status": "completed", "checkpoint_path": str(checkpoint_path),
            "corpus_examples": len(examples), "training_loss": history,
            "generation_metrics": metrics, "checkpoint_sha256": checkpoint_sha256,
            "evidence_type": "generator_training", "seed": seed,
            "hardware": _hardware_profile("cpu", torch.__version__)}


def predictor_training(job: Job) -> dict:
    """Train the predictor only from a checksum-verified NATS-Bench archive."""
    config = job.payload
    benchmark_path = config.get("benchmark_path")
    expected_checksum = config.get("benchmark_sha256")
    checkpoint_path = config.get("checkpoint_path")
    raw_indices = config.get("indices")
    if not benchmark_path or not expected_checksum or not checkpoint_path or not raw_indices:
        raise RuntimeError("predictor jobs require benchmark_path, benchmark_sha256, indices, and checkpoint_path")
    if len(raw_indices) < 3:
        raise RuntimeError("predictor jobs require at least three indices for train/validation/test")
    from pathlib import Path
    archive = Path(benchmark_path)
    allowed_path(str(archive), field="benchmark_path")
    allowed_path(str(checkpoint_path), field="checkpoint_path")
    if not archive.exists():  # a file, or an extracted NATS-Bench "-simple" directory
        raise RuntimeError(f"benchmark archive is unavailable: {archive}")
    try:
        import torch
        from archai_benchmark.adapter import NATSBenchAdapter
        from archai_benchmark.integrity import sha256_path
        from archai_core.schema import TensorSpec  # noqa: F401 - availability check
        from archai_predictor.data import split_records
        from archai_predictor.model import PerformancePredictor, PredictorConfig
        from archai_predictor.training import evaluate_predictor, fit_predictor, save_checkpoint

        from scripts.train_predictor import collect_records
    except ImportError as exc:
        raise RuntimeError("install the benchmark and ml extras for predictor workers") from exc
    actual_checksum = sha256_path(archive)
    if actual_checksum != str(expected_checksum).lower():
        raise RuntimeError("benchmark archive checksum mismatch")
    dataset = str(config.get("dataset", "cifar10"))
    search_space = str(config.get("search_space", "tss"))
    seed = int(config.get("seed", 0))
    adapter = NATSBenchAdapter(str(archive), search_space, dataset).open()
    records = collect_records(adapter, [int(index) for index in raw_indices], seed, dataset)
    splits = split_records(records, seed=seed)
    if not all(splits.values()):
        raise RuntimeError("predictor split produced an empty partition")
    model = PerformancePredictor(PredictorConfig())
    history = fit_predictor(model, splits["train"], epochs=int(config.get("epochs", 20)), seed=seed,
                            batch_size=int(config.get("batch_size", 32)))
    validation = evaluate_predictor(model, splits["validation"])
    test = evaluate_predictor(model, splits["test"])
    metadata = {"model": "ArchAI-Predictor", "dataset": dataset,
                "search_space": search_space, "seed": seed,
                "split_sizes": {key: len(value) for key, value in splits.items()},
                "test_used_for_selection": False, "archive_sha256": actual_checksum,
                "evidence_type": "benchmark_training"}
    save_checkpoint(model, checkpoint_path, metadata)
    checkpoint_sha256 = _sha256_file(checkpoint_path)
    return {"status": "completed", "checkpoint_path": str(checkpoint_path),
            "training_loss": history, "validation": validation, "test": test,
            "evidence_type": "benchmark_training", "seed": seed,
            "archive_sha256": actual_checksum, "checkpoint_sha256": checkpoint_sha256,
            "test_used_for_selection": False,
            "hardware": _hardware_profile("cpu", torch.__version__)}


def benchmark_search(job: Job) -> dict:
    """Run the configured validation-selected benchmark search.

    The archive checksum is mandatory so a worker cannot silently query an
    unverified or stale benchmark file.
    """
    algorithm = job.payload.get("algorithm", "random")
    if algorithm not in {"random", "evolution", "bayesian"}:
        raise RuntimeError("benchmark worker supports algorithm=random, evolution or bayesian")
    try:
        from archai_benchmark import (
            BenchmarkCache,
            BenchmarkEvaluator,
            IndexBayesianOptimization,
            IndexRandomSearch,
            IndexRegularizedEvolution,
            NATSBenchAdapter,
            QueryBudget,
        )
        from archai_benchmark.integrity import sha256_path
    except ImportError as exc:
        raise RuntimeError("install the benchmark extra for benchmark search workers") from exc
    path = os.getenv("ARCHAI_NATS_BENCH_PATH")
    expected_checksum = os.getenv("ARCHAI_NATS_BENCH_SHA256")
    if not path or not expected_checksum:
        raise RuntimeError("ARCHAI_NATS_BENCH_PATH and ARCHAI_NATS_BENCH_SHA256 are required")
    archive = Path(path)
    if not archive.exists():  # a file, or an extracted NATS-Bench "-simple" directory
        raise RuntimeError(f"benchmark archive is unavailable: {archive}")
    actual_checksum = sha256_path(archive)
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
    elif algorithm == "bayesian":
        architecture_strings = {index: adapter.architecture_string(index) for index in indices}
        policy = IndexBayesianOptimization(indices, architecture_strings,
                                           seed=int(config.get("seed", 0)),
                                           warmup=int(config.get("warmup", 5)),
                                           candidate_pool_size=int(config.get("candidate_pool_size", 256)))
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
        if algorithm != "random":
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
    WorkerRunner(store, {"search": benchmark_search, "training": candidate_training,
                         "generator_training": generator_training,
                         "predictor_training": predictor_training}).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
