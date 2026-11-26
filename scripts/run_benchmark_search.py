"""Run a validation-selected baseline on a real NATS-Bench archive."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai_benchmark import (
    BenchmarkCache,
    BenchmarkEvaluator,
    IndexRandomSearch,
    IndexRegularizedEvolution,
    NATSBenchAdapter,
    QueryBudget,
)
from archai_benchmark.integrity import sha256_path


def select_best_validation(records):
    if not records:
        raise ValueError("at least one benchmark result is required")
    return max(records, key=lambda record: record.validation_accuracy)


ALGORITHMS = ("random", "evolution")


def run_search(adapter, indices, *, budget: int, algorithm: str, seed: int, cache_path: Path,
               population_size: int = 8, sample_size: int = 3) -> dict:
    """Run one validation-selected benchmark search against an opened adapter.

    The held-out test accuracy of the validation-selected architecture is reported
    separately and never used for selection.
    """
    if algorithm not in ALGORITHMS:
        raise ValueError(f"unsupported algorithm: {algorithm}")
    if budget <= 0:
        raise ValueError("budget must be positive")
    evaluator = BenchmarkEvaluator(adapter, QueryBudget(min(budget, len(indices))),
                                   BenchmarkCache(cache_path))
    if algorithm == "random":
        policy = IndexRandomSearch(indices, seed=seed)
    else:
        architecture_strings = {index: adapter.architecture_string(index) for index in indices}
        policy = IndexRegularizedEvolution(indices, architecture_strings,
                                           population_size=population_size,
                                           sample_size=sample_size, seed=seed)
    records = []
    while len(records) < budget:
        index = policy.ask()
        if index is None:
            break
        record = evaluator.evaluate_index(index, seed=seed)
        records.append(record)
        if algorithm == "evolution":
            policy.tell(index, record.validation_accuracy)
    if not records:
        raise ValueError("no benchmark indices were evaluated")
    best = select_best_validation(records)
    return {"algorithm": algorithm, "seed": seed, "budget": budget, "queries": evaluator.queries,
            "selected_on": "validation_accuracy", "selected_index": best.architecture_index,
            "selected_validation_accuracy": best.validation_accuracy,
            "held_out_test_accuracy": best.test_accuracy, "evidence_type": "benchmark_lookup",
            "evaluated_indices": [record.architecture_index for record in records]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-path", required=True)
    parser.add_argument("--benchmark-sha256", required=True)
    parser.add_argument("--indices", required=True, help="comma-separated benchmark indices")
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--dataset", default="cifar10")
    parser.add_argument("--search-space", default="tss")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--algorithm", choices=("random", "evolution"), default="random")
    parser.add_argument("--population-size", type=int, default=8)
    parser.add_argument("--sample-size", type=int, default=3)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    indices = [int(value.strip()) for value in args.indices.split(",") if value.strip()]
    if args.budget <= 0:
        parser.error("budget must be positive")
    actual_checksum = sha256_path(args.benchmark_path)
    if actual_checksum != args.benchmark_sha256.lower():
        parser.error("benchmark archive checksum mismatch")
    if args.algorithm == "evolution" and (args.population_size <= 0 or args.sample_size <= 0):
        parser.error("population and sample sizes must be positive")
    adapter = NATSBenchAdapter(args.benchmark_path, args.search_space, args.dataset).open()
    try:
        report = run_search(adapter, indices, budget=args.budget, algorithm=args.algorithm,
                            seed=args.seed, cache_path=args.cache,
                            population_size=args.population_size, sample_size=args.sample_size)
    except ValueError as exc:
        parser.error(str(exc))
    report.update({"dataset": args.dataset, "search_space": args.search_space,
                   "archive_sha256": actual_checksum})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
