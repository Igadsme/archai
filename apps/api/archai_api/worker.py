"""Durable worker entry point for the API job queue."""
from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path

from archai_shared.jobs import Job, RedisJobStore
from archai_shared.paths import allowed_path
from archai_shared.worker import WorkerRunner, raise_if_cancelled, report_progress


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
    live_history: list[dict[str, float]] = []
    report_progress({"phase": "training", "epochs_completed": 0, "epochs": training_config.epochs,
                     "history": []}, force=True)

    def on_epoch_end(row: dict[str, float]) -> None:
        live_history.append(row)
        report_progress({"phase": "training", "epochs_completed": len(live_history),
                         "epochs": training_config.epochs, "history": list(live_history),
                         "evidence_type": "synthetic_training"}, force=True)
        raise_if_cancelled(force=True)

    result = train_candidate(architecture, train_loader, validation_loader, training_config,
                             checkpoint_path=checkpoint, on_epoch_end=on_epoch_end)
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



def _benchmark_indices(config: dict, path: str | Path) -> list[int]:
    """Job payload indices, or ARCHAI_NATS_BENCH_INDICES.

    The value `fixture` (or `all`) expands to every index in a fixture path so
    the hosted demo does not need a 256-long env var.
    """
    raw = config.get("indices")
    if not raw:
        raw = os.getenv("ARCHAI_NATS_BENCH_INDICES", "")
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in {"fixture", "all"}:
            from archai_benchmark.fixture import FixtureAPI, is_fixture_path
            if not is_fixture_path(path):
                raise RuntimeError("ARCHAI_NATS_BENCH_INDICES=fixture requires a fixture path")
            return FixtureAPI.from_path(path).indices()
        raw = [value for value in raw.split(",") if value.strip()]
    return [int(value) for value in raw]


def benchmark_search(job: Job) -> dict:
    """Run the configured validation-selected benchmark search.

    The archive checksum is mandatory so a worker cannot silently query an
    unverified or stale benchmark file.
    """
    try:
        from archai_benchmark import (
            BenchmarkCache,
            BenchmarkEvaluator,
            NATSBenchAdapter,
            QueryBudget,
        )
        from archai_benchmark.integrity import sha256_path
        from archai_benchmark.policy_registry import ALGORITHMS, POLICIES, available, build_policy
        from archai_benchmark.research_metrics import hypervolume_2d
    except ImportError as exc:
        raise RuntimeError("install the benchmark extra for benchmark search workers") from exc
    algorithm = job.payload.get("algorithm", "random")
    if algorithm not in POLICIES:
        raise RuntimeError(f"benchmark worker supports algorithm={', '.join(ALGORITHMS)}")
    usable, reason = available(algorithm)
    if not usable:
        raise RuntimeError(f"{algorithm} is unavailable on this worker: {reason}")
    params = dict(job.payload.get("params") or {})
    legacy_defaults = {"bayesian": {"warmup": 5, "candidate_pool_size": 256},
                       "evolution": {"population_size": 8, "sample_size": 3}}.get(algorithm, {})
    for key, default in legacy_defaults.items():  # top-level keys predate the params object
        params.setdefault(key, job.payload.get(key, default))
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
    indices = _benchmark_indices(config, path)
    if not indices:
        raise RuntimeError("no benchmark indices configured")
    dataset = str(config.get("dataset_id", "cifar10"))
    search_space = os.getenv("ARCHAI_NATS_BENCH_SEARCH_SPACE", "tss")
    cache_path = os.getenv("ARCHAI_BENCHMARK_CACHE", "/tmp/archai-benchmark-cache.sqlite")
    adapter = NATSBenchAdapter(str(archive), search_space, dataset).open()
    pool_before = len(indices)
    constraints_payload = config.get("constraints")
    if constraints_payload:
        from archai_benchmark.constraint_filter import feasible_benchmark_indices
        from archai_shared.constraints import ArchitectureConstraints
        constraints = ArchitectureConstraints.model_validate(constraints_payload)
        if not constraints.is_empty():
            feasible, unevaluable = feasible_benchmark_indices(adapter, indices, constraints)
            if unevaluable:
                raise RuntimeError("constraints cannot be evaluated on this benchmark: " + ", ".join(unevaluable))
            if not feasible:
                raise RuntimeError("no architectures in the pool satisfy the constraints")
            indices = feasible
    budget = min(int(config["budget_evaluations"]), len(indices))
    evaluator = BenchmarkEvaluator(adapter, QueryBudget(budget), BenchmarkCache(cache_path))
    policy = build_policy(adapter, indices, algorithm, int(config.get("seed", 0)), params)
    uses_cost = getattr(policy, "uses_cost", False)
    records, costs = [], []
    best_so_far: float | None = None
    report_progress({"phase": "searching", "evaluations": 0, "budget": budget}, force=True)
    while len(records) < budget:
        raise_if_cancelled()
        index = policy.ask()
        if index is None:
            break
        record = evaluator.evaluate_index(index, seed=int(config.get("seed", 0)))
        records.append(record)
        cost = adapter.cost(index) if callable(getattr(adapter, "cost", None)) else None
        costs.append(cost)
        if uses_cost:
            policy.tell(index, record.validation_accuracy, cost)
        elif hasattr(policy, "tell"):
            policy.tell(index, record.validation_accuracy)
        if best_so_far is None or record.validation_accuracy > best_so_far:
            best_so_far = record.validation_accuracy
        report_progress({"phase": "searching", "evaluations": len(records), "budget": budget,
                         "best_validation_accuracy": best_so_far, "evidence_type": "benchmark_lookup"},
                        force=len(records) == budget)
    if not records:
        raise RuntimeError("benchmark search evaluated no architectures")
    history = [{"step": step, "index": record.architecture_index,
                "architecture_string": record.architecture_string,
                "validation_accuracy": record.validation_accuracy,
                **({"params_m": cost["params_m"], "flops_m": cost["flops_m"]} if cost else {})}
               for step, (record, cost) in enumerate(zip(records, costs), start=1)]
    extras = {}
    if all(costs):
        extras["hypervolume_validation_params"] = hypervolume_2d(
            [(record.validation_accuracy, cost["params_m"]) for record, cost in zip(records, costs)], (0.0, 1.6))
    best = max(records, key=lambda record: record.validation_accuracy)
    return {"algorithm": algorithm, "dataset": dataset, "search_space": search_space,
            "seed": int(config.get("seed", 0)), "budget": int(config["budget_evaluations"]),
            "queries": evaluator.queries, "evaluations": len(records),
            "cache_hits": len(records) - evaluator.queries, "selected_on": "validation_accuracy",
            "selected_index": best.architecture_index,
            "selected_architecture_string": best.architecture_string,
            "selected_validation_accuracy": best.validation_accuracy,
            "held_out_test_accuracy": best.test_accuracy,
            "evidence_type": "benchmark_lookup",
            "evaluated_indices": [record.architecture_index for record in records],
            "history": history, "policy_params": params, **extras,
            "archive_sha256": actual_checksum,
            "pool_size_before_constraints": pool_before,
            "pool_size_after_constraints": len(indices)}


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
