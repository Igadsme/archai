"""Train the ArchAI-V1 generator on real NATS-Bench TSS cells (CPU smoke scale).

Data: the benchmark table written by `scripts/benchmark_table.py` (benchmark lookups,
verified archive). The generator models p(six edge operations | condition), where the
condition is (validation-accuracy quantile, parameter budget fraction) of each training
cell. Cells are split by architecture into train / held-out; nothing is selected on test
accuracy. Generated cells are scored by benchmark lookup of their validation accuracy
(evidence type `benchmark_lookup`); the generator itself is never shown test accuracy.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import subprocess
from pathlib import Path
from statistics import mean

from archai_benchmark.learned_search import NB201_OPS
from archai_generator.model import ArchitectureGenerator, GeneratorConfig
from archai_generator.training import fit_sequences, load_checkpoint, save_checkpoint
from archai_shared.registry import sha256_file

MAX_PARAMS_M = 1.6


def revision() -> str:
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD"]).returncode != 0
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return head + ("+dirty" if dirty else "")


def operations_of(encoding: str) -> tuple[str, ...]:
    from archai_benchmark.nasbench201 import parse_architecture_string
    return parse_architecture_string(encoding).operations


def connected(operations) -> bool:
    """True when some path of non-`none` edges links cell input (node 0) to output (node 3)."""
    edges = [(0, 1), (0, 2), (1, 2), (0, 3), (1, 3), (2, 3)]
    reach = {0}
    for source, target in edges:  # edges are in topological order
        if source in reach and operations[edges.index((source, target))] != "none":
            reach.add(target)
    return 3 in reach


def hamming(a, b) -> int:
    return sum(x != y for x, y in zip(a, b))


def load_table(path: Path, trial: int) -> dict[tuple[str, ...], dict]:
    table = {}
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            table[operations_of(row["architecture_string"])] = {
                "index": row["index"], "validation_accuracy": row["trials"][trial]["validation_accuracy"],
                "params_m": row["params_m"]}
    return table


def quantile_of(value: float, sorted_values: list[float]) -> float:
    import bisect
    return bisect.bisect_left(sorted_values, value) / max(1, len(sorted_values) - 1)


def generation_report(samples, table, train_set, *, params_budget_m: float) -> dict:
    unique = list(dict.fromkeys(tuple(sample) for sample in samples))
    in_space = [cell for cell in unique if cell in table]
    rows = [table[cell] for cell in in_space]
    pairs = list(itertools.combinations(unique[:300], 2))
    return {
        "samples": len(samples),
        "validity_in_search_space": sum(tuple(s) in table for s in samples) / len(samples),
        "validity_connected": sum(connected(s) for s in samples) / len(samples),
        "uniqueness": len(unique) / len(samples),
        "novelty_vs_training_cells": sum(cell not in train_set for cell in unique) / len(unique),
        "diversity_mean_pairwise_hamming": mean(hamming(a, b) for a, b in pairs) if pairs else 0.0,
        "constraint_satisfaction_params": sum(row["params_m"] <= params_budget_m for row in rows) / len(rows),
        "candidate_quality_mean_validation_accuracy": mean(row["validation_accuracy"] for row in rows),
        "candidate_quality_best_validation_accuracy": max(row["validation_accuracy"] for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--train-cells", type=int, default=2000)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--trial", type=int, default=0, help="which archive trial (0..2) supplies validation accuracy")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    table = load_table(args.table, args.trial)
    cells = sorted(table)
    rng = random.Random(args.seed)
    rng.shuffle(cells)
    train_cells = cells[:args.train_cells]
    train_set = set(train_cells)
    accuracies = sorted(table[cell]["validation_accuracy"] for cell in train_cells)
    conditions = [(quantile_of(table[cell]["validation_accuracy"], accuracies),
                   table[cell]["params_m"] / MAX_PARAMS_M) for cell in train_cells]
    import torch
    torch.manual_seed(args.seed)
    config = GeneratorConfig(latent_dim=8, hidden_dim=64, max_nodes=6, condition_dim=2, vocabulary=NB201_OPS)
    model = ArchitectureGenerator(config)
    history = fit_sequences(model, [list(cell) for cell in train_cells], conditions=conditions,
                            epochs=args.epochs, lr=3e-3, seed=args.seed)
    metadata = {"model": "ArchAI-V1", "kind": "generator", "scale": "cpu_smoke",
                "search_space": "nats-bench-tss", "dataset": "cifar10-valid (validation accuracy)",
                "train_cells": len(train_cells), "epochs": args.epochs, "seed": args.seed,
                "archive_trial": args.trial, "condition": ["validation_accuracy_quantile", "params_m / 1.6"],
                "code_revision": revision(), "test_used_for_selection": False}
    save_checkpoint(model, args.checkpoint, metadata)
    checkpoint_sha256 = sha256_file(args.checkpoint)
    reloaded = ArchitectureGenerator(config)
    load_checkpoint(reloaded, args.checkpoint)
    same = (model.sample_tokens(32, steps=6, seed=99, condition=(0.95, 0.5)) ==
            reloaded.sample_tokens(32, steps=6, seed=99, condition=(0.95, 0.5)))
    budget = 0.8
    settings = {"high_accuracy_within_0.8M_params": (0.95, budget / MAX_PARAMS_M),
                "low_accuracy": (0.05, 0.5)}
    reports = {name: generation_report(model.sample_tokens(args.samples, steps=6, seed=args.seed + 1, condition=cond),
                                       table, train_set, params_budget_m=budget)
               for name, cond in settings.items()}
    uniform = [[rng.choice(NB201_OPS) for _ in range(6)] for _ in range(args.samples)]
    reports["uniform_random_cells_baseline"] = generation_report(uniform, table, train_set, params_budget_m=budget)
    untrained = ArchitectureGenerator(config)
    reports["untrained_generator_baseline"] = generation_report(
        untrained.sample_tokens(args.samples, steps=6, seed=args.seed + 1, condition=(0.95, budget / MAX_PARAMS_M)),
        table, train_set, params_budget_m=budget)
    output = {"metadata": metadata, "checkpoint": str(args.checkpoint), "checkpoint_sha256": checkpoint_sha256,
              "checkpoint_reload_reproduces_samples": same,
              "training_loss_first_last": [history[0], history[-1]],
              "evidence_type": {"training_loss": "measured_training",
                                "candidate_quality": "benchmark_lookup of generated cells"},
              "params_budget_m": budget, "generation": reports}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(output, indent=2, sort_keys=True))
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
