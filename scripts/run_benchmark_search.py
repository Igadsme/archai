"""Run a validation-selected baseline on a real NATS-Bench archive."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai_benchmark import (BenchmarkCache, BenchmarkEvaluator, IndexRandomSearch,
                               IndexRegularizedEvolution, NATSBenchAdapter, QueryBudget)


def select_best_validation(records):
    if not records:
        raise ValueError("at least one benchmark result is required")
    return max(records, key=lambda record: record.validation_accuracy)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-path", required=True)
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
    if args.algorithm == "evolution" and (args.population_size <= 0 or args.sample_size <= 0):
        parser.error("population and sample sizes must be positive")
    adapter = NATSBenchAdapter(args.benchmark_path, args.search_space, args.dataset).open()
    evaluator = BenchmarkEvaluator(adapter, QueryBudget(min(args.budget, len(indices))), BenchmarkCache(args.cache))
    if args.algorithm == "random":
        policy = IndexRandomSearch(indices, seed=args.seed)
    else:
        architecture_strings = {index: adapter.architecture_string(index) for index in indices}
        policy = IndexRegularizedEvolution(indices, architecture_strings,
                                           population_size=args.population_size,
                                           sample_size=args.sample_size, seed=args.seed)
    records = []
    while len(records) < args.budget:
        index = policy.ask()
        if index is None:
            break
        record = evaluator.evaluate_index(index, seed=args.seed)
        records.append(record)
        if args.algorithm == "evolution":
            policy.tell(index, record.validation_accuracy)
    if not records:
        parser.error("no benchmark indices were evaluated")
    best = select_best_validation(records)
    report = {"algorithm": args.algorithm, "dataset": args.dataset, "search_space": args.search_space,
              "seed": args.seed, "budget": args.budget, "queries": evaluator.queries,
              "selected_on": "validation_accuracy", "selected_index": best.architecture_index,
              "selected_validation_accuracy": best.validation_accuracy,
              "held_out_test_accuracy": best.test_accuracy, "evidence_type": "benchmark_lookup",
              "evaluated_indices": [record.architecture_index for record in records]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
