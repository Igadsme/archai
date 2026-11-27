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
from archai_generator.budget import CONDITION_DIM, MAX_PARAMS_M, encode_condition, eval_condition
from archai_generator.model import ArchitectureGenerator, GeneratorConfig
from archai_generator.training import fit_sequences, load_checkpoint, save_checkpoint
from archai_shared.registry import sha256_file


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
                "index": row["index"],
                "validation_accuracy": row["trials"][trial]["validation_accuracy"],
                "params_m": row["params_m"],
            }
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
        "constraint_satisfaction_params": sum(row["params_m"] <= params_budget_m for row in rows)
        / len(rows),
        "candidate_quality_mean_validation_accuracy": mean(
            row["validation_accuracy"] for row in rows
        ),
        "candidate_quality_best_validation_accuracy": max(
            row["validation_accuracy"] for row in rows
        ),
    }


def _rejection_aware_epochs(
    model, table, *, epochs: int, seed: int, batch: int = 128, params_budget_m: float = 0.8
) -> list[float]:
    """Self-train on feasible samples and penalize in-table cells that exceed the budget.

    Sampling is not differentiated; log-probabilities are obtained from a teacher-forced
    forward pass on the sampled tokens (REINFORCE-style for violators, MLE for feasible).
    """
    import torch
    import torch.nn.functional as F
    from archai_generator.budget import eval_condition

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    condition = eval_condition(0.95, params_budget_m)
    vocab = model.config.vocabulary
    history = []
    model.train()
    for epoch in range(epochs):
        samples = model.sample_tokens(batch, steps=6, seed=seed + epoch, condition=condition)
        cells = [tuple(sample) for sample in samples]
        feasible, violators = [], []
        for cell in cells:
            if cell not in table:
                continue
            if table[cell]["params_m"] <= params_budget_m:
                feasible.append(cell)
            else:
                violators.append(cell)
        loss_terms = []
        if feasible:
            targets = torch.tensor(
                [[vocab.index(token) for token in cell] for cell in feasible], dtype=torch.long
            )
            cond = torch.tensor([list(condition)] * len(feasible), dtype=torch.float32)
            latent = torch.randn(len(feasible), model.config.latent_dim)
            logits = model.forward(latent, cond, teacher_tokens=targets)
            loss_terms.append(F.cross_entropy(logits.transpose(1, 2), targets))
        if violators:
            targets = torch.tensor(
                [[vocab.index(token) for token in cell] for cell in violators], dtype=torch.long
            )
            cond = torch.tensor([list(condition)] * len(violators), dtype=torch.float32)
            latent = torch.randn(len(violators), model.config.latent_dim)
            logits = model.forward(latent, cond, teacher_tokens=targets)
            log_prob = (
                F.log_softmax(logits, dim=-1)
                .gather(-1, targets.unsqueeze(-1))
                .squeeze(-1)
                .mean(dim=1)
            )
            excess = torch.tensor(
                [table[cell]["params_m"] - params_budget_m for cell in violators],
                dtype=torch.float32,
            )
            loss_terms.append((excess.clamp(min=0) * log_prob).mean())
        if not loss_terms:
            history.append(float("nan"))
            continue
        loss = sum(loss_terms)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
    return history


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--train-cells", type=int, default=2000)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument(
        "--trial",
        type=int,
        default=0,
        help="which archive trial (0..2) supplies validation accuracy",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--condition-mode",
        choices=("point", "ceiling", "ceiling_bins"),
        default="point",
        help="point uses each cell's own params_m/1.6; ceiling samples a budget "
        "in [params_m, 1.6]; ceiling_bins adds a one-hot budget bin, tight-budget "
        "oversampling, and a rejection-aware penalty",
    )
    parser.add_argument(
        "--penalty-epochs",
        type=int,
        default=0,
        help="extra rejection-aware epochs used by ceiling_bins; measured 40-epoch runs improved satisfaction to 1.0 but dropped mean val acc below random, so the default is 0",
    )
    parser.add_argument(
        "--reject-samples",
        type=int,
        default=0,
        help="if >0, also report hard-rejection sampling of this many feasible cells",
    )
    args = parser.parse_args()
    table = load_table(args.table, args.trial)
    cells = sorted(table)
    rng = random.Random(args.seed)
    rng.shuffle(cells)
    train_cells = cells[: args.train_cells]
    train_set = set(train_cells)
    accuracies = sorted(table[cell]["validation_accuracy"] for cell in train_cells)
    sequences = [list(cell) for cell in train_cells]
    weights = None
    if args.condition_mode == "point":
        conditions = [
            (
                quantile_of(table[cell]["validation_accuracy"], accuracies),
                table[cell]["params_m"] / MAX_PARAMS_M,
            )
            for cell in train_cells
        ]
        condition_label = "validation_accuracy_quantile, params_m / 1.6 (point estimate)"
        condition_dim = 2
    elif args.condition_mode == "ceiling":
        conditions = []
        for cell in train_cells:
            params_m = table[cell]["params_m"]
            ceiling = rng.uniform(params_m, MAX_PARAMS_M)
            conditions.append(
                (
                    quantile_of(table[cell]["validation_accuracy"], accuracies),
                    ceiling / MAX_PARAMS_M,
                )
            )
        condition_label = (
            "validation_accuracy_quantile, sampled budget ceiling in [params_m, 1.6] / 1.6"
        )
        condition_dim = 2
    else:
        sequences, conditions, weights = [], [], []
        eval_budget = 0.8
        for cell in train_cells:
            params_m = table[cell]["params_m"]
            acc_q = quantile_of(table[cell]["validation_accuracy"], accuracies)
            tight_hi = min(MAX_PARAMS_M, params_m + 0.2)
            ceilings = [
                rng.uniform(params_m, tight_hi),
                rng.uniform(params_m, MAX_PARAMS_M),
                MAX_PARAMS_M,
            ]
            if params_m <= eval_budget:
                ceilings.append(eval_budget)
            for ceiling in ceilings:
                sequences.append(list(cell))
                conditions.append(encode_condition(acc_q, ceiling / MAX_PARAMS_M))
                tight = ceiling <= eval_budget + 1e-9
                high = acc_q >= 0.8
                weights.append(4.0 if tight and high else (2.0 if tight else 1.0))
        condition_label = (
            "validation_accuracy_quantile, ceiling/1.6, 6-bin one-hot of the ceiling; "
            "tight-budget oversampling and rejection-aware penalty"
        )
        condition_dim = CONDITION_DIM
    import torch

    torch.manual_seed(args.seed)
    config = GeneratorConfig(
        latent_dim=8, hidden_dim=64, max_nodes=6, condition_dim=condition_dim, vocabulary=NB201_OPS
    )
    model = ArchitectureGenerator(config)
    history = fit_sequences(
        model,
        sequences,
        conditions=conditions,
        weights=weights,
        epochs=args.epochs,
        lr=3e-3,
        seed=args.seed,
    )
    if args.condition_mode == "ceiling_bins" and args.penalty_epochs > 0:
        history.extend(
            _rejection_aware_epochs(model, table, epochs=args.penalty_epochs, seed=args.seed + 17)
        )
    metadata = {
        "model": "ArchAI-V1",
        "kind": "generator",
        "scale": "cpu_smoke",
        "search_space": "nats-bench-tss",
        "dataset": "cifar10-valid (validation accuracy)",
        "train_cells": len(train_cells),
        "epochs": args.epochs,
        "seed": args.seed,
        "archive_trial": args.trial,
        "condition": condition_label,
        "condition_mode": args.condition_mode,
        "penalty_epochs": args.penalty_epochs,
        "code_revision": revision(),
        "test_used_for_selection": False,
    }
    save_checkpoint(model, args.checkpoint, metadata)
    checkpoint_sha256 = sha256_file(args.checkpoint)
    reloaded = ArchitectureGenerator(config)
    load_checkpoint(reloaded, args.checkpoint)
    budget = 0.8
    high_cond = (
        eval_condition(0.95, budget)
        if condition_dim == CONDITION_DIM
        else (0.95, budget / MAX_PARAMS_M)
    )
    low_cond = eval_condition(0.05, budget) if condition_dim == CONDITION_DIM else (0.05, 0.5)
    same = model.sample_tokens(32, steps=6, seed=99, condition=high_cond) == reloaded.sample_tokens(
        32, steps=6, seed=99, condition=high_cond
    )
    settings = {"high_accuracy_within_0.8M_params": high_cond, "low_accuracy": low_cond}
    reports = {
        name: generation_report(
            model.sample_tokens(args.samples, steps=6, seed=args.seed + 1, condition=cond),
            table,
            train_set,
            params_budget_m=budget,
        )
        for name, cond in settings.items()
    }
    uniform = [[rng.choice(NB201_OPS) for _ in range(6)] for _ in range(args.samples)]
    reports["uniform_random_cells_baseline"] = generation_report(
        uniform, table, train_set, params_budget_m=budget
    )
    untrained = ArchitectureGenerator(config)
    reports["untrained_generator_baseline"] = generation_report(
        untrained.sample_tokens(args.samples, steps=6, seed=args.seed + 1, condition=high_cond),
        table,
        train_set,
        params_budget_m=budget,
    )
    if args.reject_samples > 0:
        target = args.reject_samples
        accepted, draws = [], 0
        seed = args.seed + 11
        while len(accepted) < target and draws < target * 40:
            batch = model.sample_tokens(
                min(256, target * 4), steps=6, seed=seed + draws, condition=high_cond
            )
            draws += len(batch)
            for cell in batch:
                cell = tuple(cell)
                if cell in table and table[cell]["params_m"] <= budget:
                    accepted.append(cell)
                    if len(accepted) >= target:
                        break
        feasible_random = [cell for cell in table if table[cell]["params_m"] <= budget]
        rng_eval = random.Random(args.seed + 13)
        random_feasible = (
            [
                feasible_random[rng_eval.randrange(len(feasible_random))]
                for _ in range(len(accepted))
            ]
            if feasible_random and accepted
            else []
        )
        reports["hard_reject_to_0.8M_params"] = {
            "requested": target,
            "accepted": len(accepted),
            "draws": draws,
            "yield": (len(accepted) / draws) if draws else 0.0,
            "candidate_quality_mean_validation_accuracy": mean(
                table[cell]["validation_accuracy"] for cell in accepted
            )
            if accepted
            else None,
            "random_feasible_mean_validation_accuracy": mean(
                table[cell]["validation_accuracy"] for cell in random_feasible
            )
            if random_feasible
            else None,
            "evidence_type": "benchmark_lookup",
        }
    output = {
        "metadata": metadata,
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_reload_reproduces_samples": same,
        "training_loss_first_last": [history[0], history[-1]],
        "training_loss_len": len(history),
        "evidence_type": {
            "training_loss": "measured_training",
            "candidate_quality": "benchmark_lookup of generated cells",
        },
        "params_budget_m": budget,
        "generation": reports,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(output, indent=2, sort_keys=True))
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
