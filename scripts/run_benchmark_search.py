"""Run a validation-selected baseline on a real NATS-Bench archive."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai_benchmark import (
    BenchmarkCache,
    BenchmarkEvaluator,
    NATSBenchAdapter,
    QueryBudget,
)
from archai_benchmark.integrity import sha256_path
from archai_benchmark.policy_registry import ALGORITHMS, POLICIES, build_policy
from archai_benchmark.research_metrics import hypervolume_2d


def select_best_validation(records):
    if not records:
        raise ValueError("at least one benchmark result is required")
    return max(records, key=lambda record: record.validation_accuracy)


EVOLUTION_PARAMS = POLICIES["evolution"]["params"]
BAYESIAN_PARAMS = POLICIES["bayesian"]["params"]
POLICY_PARAMS = {name: spec["params"] for name, spec in POLICIES.items()}
# Declared before any run: (validation accuracy %, parameters in millions). Every NATS-Bench
# TSS cell has fewer than 1.6M parameters, so the reference point is dominated by all cells.
HYPERVOLUME_REFERENCE = (0.0, 1.6)


def run_search(adapter, indices, *, budget: int, algorithm: str, seed: int, cache_path: Path,
               population_size: int | None = None, sample_size: int | None = None,
               params: dict | None = None) -> dict:
    """Run one validation-selected benchmark search against an opened adapter.

    The held-out test accuracy of the validation-selected architecture is reported
    separately and never used for selection or passed to the policy.
    """
    if budget <= 0:
        raise ValueError("budget must be positive")
    params = dict(params or {})
    if algorithm == "evolution":
        if population_size is not None:
            params.setdefault("population_size", population_size)
        if sample_size is not None:
            params.setdefault("sample_size", sample_size)
    policy = build_policy(adapter, indices, algorithm, seed, params)
    evaluator = BenchmarkEvaluator(adapter, QueryBudget(min(budget, len(indices))),
                                   BenchmarkCache(cache_path))
    records, costs = [], []
    has_cost = callable(getattr(adapter, "cost", None))
    if getattr(policy, "uses_cost", False) and not has_cost:
        raise ValueError(f"{algorithm} needs an adapter that exposes static cell costs")
    while len(records) < budget:
        index = policy.ask()
        if index is None:
            break
        record = evaluator.evaluate_index(index, seed=seed)
        records.append(record)
        cost = adapter.cost(index) if has_cost else None
        costs.append(cost)
        if getattr(policy, "uses_cost", False):
            policy.tell(index, record.validation_accuracy, cost)
        elif hasattr(policy, "tell"):
            policy.tell(index, record.validation_accuracy)
    if not records:
        raise ValueError("no benchmark indices were evaluated")
    best = select_best_validation(records)
    extras = {}
    if has_cost:
        extras["hypervolume_validation_params"] = hypervolume_2d(
            [(record.validation_accuracy, cost["params_m"]) for record, cost in zip(records, costs)],
            HYPERVOLUME_REFERENCE)
        extras["hypervolume_reference"] = list(HYPERVOLUME_REFERENCE)
        extras["selected_params_m"] = costs[records.index(best)]["params_m"]
    if hasattr(policy, "fallbacks"):
        extras["policy_random_fallbacks"] = policy.fallbacks
    return {**extras,"algorithm": algorithm, "seed": seed, "budget": budget, "queries": evaluator.queries,
            "policy_params": params,
            "selected_on": "validation_accuracy", "selected_index": best.architecture_index,
            "selected_validation_accuracy": best.validation_accuracy,
            "held_out_test_accuracy": best.test_accuracy, "evidence_type": "benchmark_lookup",
            "evaluated_indices": [record.architecture_index for record in records],
            "validation_trace": [record.validation_accuracy for record in records]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-path", required=True)
    parser.add_argument("--benchmark-sha256", required=True)
    parser.add_argument("--indices", required=True, help="comma-separated benchmark indices")
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--dataset", default="cifar10")
    parser.add_argument("--search-space", default="tss")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--algorithm", choices=ALGORITHMS, default="random")
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
