#!/usr/bin/env python3
"""Train ArchAI-V1 on a Kaggle GPU session, or a tiny CPU smoke path.

Default hyperparameters are a planned non-smoke recipe intended to fit about
nine hours of Kaggle GPU (inside a 12-hour session). That wall-clock budget is
a plan, not a measured GPU time, until a Kaggle run records it in metrics.json.
Use --smoke for the tiny CPU path used in CI and on the box: the committed
256-cell fixture, a few epochs, and synthetic candidate training (no CIFAR-10
download, no official archive).

CIFAR-10 train-and-evaluate of generated cells uses this repo's training
engine. That is a real measured_training run, not a reproduction of the
official NATS-Bench 200-epoch SGD protocol.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_CELLS = ROOT / "datasets/fixtures/natsbench-tss-cifar10-256/cells.jsonl"
# Planned (not measured on GPU) defaults for a ~9 h Kaggle session.
DEFAULT_GENERATOR_CELLS = 15625
DEFAULT_GENERATOR_EPOCHS = 2000
DEFAULT_PREDICTOR_EPOCHS = 80
DEFAULT_CIFAR_ARCHITECTURES = 4
DEFAULT_CIFAR_EPOCHS = 80


def sha256_file(path: Path) -> str:
    from archai_shared.registry import sha256_file as digest

    return digest(path)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def device_of(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def find_table(args: argparse.Namespace) -> Path:
    if args.table and Path(args.table).is_file():
        return Path(args.table)
    if args.smoke and FIXTURE_CELLS.is_file():
        return FIXTURE_CELLS
    raise SystemExit(
        "no architecture table found; pass --table to a cifar10 JSONL "
        "(built by scripts/benchmark_table.py), or use --smoke with the committed fixture"
    )


def load_generator_from_checkpoint(checkpoint: Path):
    import torch
    from archai_generator.model import ArchitectureGenerator, GeneratorConfig
    from archai_generator.training import load_checkpoint

    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    saved = dict(payload.get("state_dict", {}).get("config") or {})
    if "vocabulary" in saved:
        saved["vocabulary"] = tuple(saved["vocabulary"])
    model = ArchitectureGenerator(GeneratorConfig(**saved) if saved else GeneratorConfig())
    load_checkpoint(model, checkpoint)
    return model


def train_generator(args: argparse.Namespace, table_path: Path, output: Path, deadline: float) -> dict:
    import torch
    from archai_benchmark.learned_search import NB201_OPS
    from archai_generator.budget import CONDITION_DIM, MAX_PARAMS_M, encode_condition
    from archai_generator.model import ArchitectureGenerator, GeneratorConfig
    from archai_generator.training import fit_sequences, load_checkpoint, save_checkpoint

    from scripts.train_generator_nb201 import load_table, quantile_of, revision

    table = load_table(table_path, trial=0)
    cells = sorted(table)
    rng = random.Random(args.seed)
    rng.shuffle(cells)
    train_cells = cells[: args.generator_cells]
    accuracies = sorted(table[cell]["validation_accuracy"] for cell in train_cells)
    sequences, conditions, weights = [], [], []
    for cell in train_cells:
        params_m = table[cell]["params_m"]
        acc_q = quantile_of(table[cell]["validation_accuracy"], accuracies)
        tight_hi = min(MAX_PARAMS_M, params_m + 0.2)
        ceilings = [
            rng.uniform(params_m, tight_hi),
            rng.uniform(params_m, MAX_PARAMS_M),
            MAX_PARAMS_M,
        ]
        if params_m <= 0.8:
            ceilings.append(0.8)
        for ceiling in ceilings:
            sequences.append(list(cell))
            conditions.append(encode_condition(acc_q, ceiling / MAX_PARAMS_M))
            tight = ceiling <= 0.8 + 1e-9
            weights.append(4.0 if tight and acc_q >= 0.8 else (2.0 if tight else 1.0))

    torch.manual_seed(args.seed)
    config = GeneratorConfig(
        latent_dim=16 if not args.smoke else 8,
        hidden_dim=128 if not args.smoke else 64,
        max_nodes=6,
        condition_dim=CONDITION_DIM,
        vocabulary=NB201_OPS,
    )
    model = ArchitectureGenerator(config)
    checkpoint = output / "generator.pt"
    state_path = output / "generator_state.json"
    start_epoch = 0
    history: list[float] = []
    if args.resume and checkpoint.is_file():
        load_checkpoint(model, checkpoint)
        if state_path.is_file():
            prior = json.loads(state_path.read_text())
            start_epoch = int(prior.get("epochs_completed", 0))
            history = list(prior.get("history") or [])
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    chunk = 2 if args.smoke else 50
    next_checkpoint = time.time() + args.checkpoint_minutes * 60
    target_epochs = args.generator_epochs
    for start in range(start_epoch, target_epochs, chunk):
        if time.time() >= deadline:
            break
        n = min(chunk, target_epochs - start)
        history.extend(
            fit_sequences(
                model,
                sequences,
                conditions=conditions,
                weights=weights,
                epochs=n,
                lr=3e-3,
                seed=args.seed + start,
                optimizer=optimizer,
            )
        )
        completed = start + n
        meta = {
            "model": "ArchAI-V1",
            "kind": "generator",
            "scale": "cpu_smoke" if args.smoke else "kaggle_gpu_planned",
            "train_cells": len(train_cells),
            "epochs": target_epochs,
            "epochs_completed": completed,
            "seed": args.seed,
            "condition_mode": "ceiling_bins",
            "code_revision": revision(),
            "test_used_for_selection": False,
            "wall_time_budget_hours": args.time_budget_hours,
            "wall_time_is_measured_gpu": False,
        }
        save_checkpoint(model, checkpoint, meta)
        write_json(
            state_path,
            {
                "epochs_completed": completed,
                "history": history,
                "checkpoint_sha256": sha256_file(checkpoint),
            },
        )
        if time.time() >= next_checkpoint:
            next_checkpoint = time.time() + args.checkpoint_minutes * 60
    return {
        "kind": "generator",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint) if checkpoint.is_file() else None,
        "epochs_completed": len(history),
        "epochs_requested": target_epochs,
        "train_cells": len(train_cells),
        "training_loss_first_last": [history[0], history[-1]] if history else None,
        "evidence_type": "measured_training",
        "scale": "cpu_smoke" if args.smoke else "kaggle_gpu_planned",
        "stopped_for_time_budget": time.time() >= deadline,
    }


def _records_from_table(table_path: Path, trial: int, cells: list[tuple[str, ...]]):
    from archai_benchmark.nasbench201 import architecture_from_string, parse_architecture_string
    from archai_core.schema import TensorSpec
    from archai_predictor.data import ArchitectureRecord

    by_ops: dict[tuple[str, ...], dict] = {}
    for line in table_path.read_text().splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        by_ops[tuple(parse_architecture_string(raw["architecture_string"]).operations)] = raw
    input_spec = TensorSpec(channels=3, height=32, width=32)
    records = []
    for cell in cells:
        raw = by_ops.get(tuple(cell))
        if raw is None:
            continue
        accuracy = float(raw["trials"][trial]["validation_accuracy"]) / 100.0
        architecture = architecture_from_string(
            raw["architecture_string"], input_spec=input_spec, output_classes=10
        )
        records.append(
            ArchitectureRecord(
                architecture,
                accuracy,
                (1.0,) + (0.0,) * 7,
                "fixture" if "fixture" in str(table_path) else "NATS-Bench table",
            )
        )
    return records


def train_predictor(args: argparse.Namespace, table_path: Path, output: Path, deadline: float) -> dict:
    import torch
    from archai_predictor.data import split_records
    from archai_predictor.model import PerformancePredictor, PredictorConfig
    from archai_predictor.training import (
        evaluate_predictor,
        fit_predictor,
        load_checkpoint,
        save_checkpoint,
    )

    from scripts.train_generator_nb201 import load_table, revision

    table = load_table(table_path, trial=0)
    cells = sorted(table)
    rng = random.Random(args.seed)
    rng.shuffle(cells)
    train_cells = cells[: args.predictor_cells]
    records = _records_from_table(table_path, 0, train_cells)
    if len(records) < 5:
        return {"kind": "predictor", "skipped": True, "reason": "need at least five cells"}
    fractions = (0.6, 0.2, 0.2) if len(records) < 30 else (0.8, 0.1, 0.1)
    splits = split_records(records, seed=args.seed, fractions=fractions)
    if not splits["train"]:
        return {"kind": "predictor", "skipped": True, "reason": "empty train split"}
    torch.manual_seed(args.seed)
    model = PerformancePredictor(PredictorConfig())
    checkpoint = output / "predictor.pt"
    state_path = output / "predictor_state.json"
    history: list[float] = []
    start_epoch = 0
    if args.resume and checkpoint.is_file():
        load_checkpoint(model, checkpoint)
        if state_path.is_file():
            prior = json.loads(state_path.read_text())
            start_epoch = int(prior.get("epochs_completed", 0))
            history = list(prior.get("history") or [])
    chunk = 1 if args.smoke else 10
    target_epochs = args.predictor_epochs
    for start in range(start_epoch, target_epochs, chunk):
        if time.time() >= deadline:
            break
        n = min(chunk, target_epochs - start)
        history.extend(
            fit_predictor(
                model,
                splits["train"],
                epochs=n,
                seed=args.seed + start,
                batch_size=8 if args.smoke else 64,
            )
        )
        completed = start + n
        meta = {
            "model": "ArchAI-V1",
            "kind": "predictor",
            "scale": "cpu_smoke" if args.smoke else "kaggle_gpu_planned",
            "epochs": target_epochs,
            "epochs_completed": completed,
            "seed": args.seed,
            "code_revision": revision(),
            "test_used_for_selection": False,
            "split_sizes": {name: len(values) for name, values in splits.items()},
        }
        save_checkpoint(model, checkpoint, meta)
        write_json(
            state_path,
            {
                "epochs_completed": completed,
                "history": history,
                "checkpoint_sha256": sha256_file(checkpoint),
            },
        )
    held_out_split = "test" if splits["test"] else "validation"
    held_out_records = splits[held_out_split]
    held_out = evaluate_predictor(model, held_out_records) if held_out_records else None
    return {
        "kind": "predictor",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint) if checkpoint.is_file() else None,
        "epochs_completed": len(history),
        "epochs_requested": target_epochs,
        "train_records": len(splits["train"]),
        "held_out_split": held_out_split,
        "held_out_metrics": held_out,
        "held_out_evidence": "predicted outputs scored against benchmark_lookup labels; test not used for selection",
        "training_evidence": "measured_training",
        "scale": "cpu_smoke" if args.smoke else "kaggle_gpu_planned",
        "stopped_for_time_budget": time.time() >= deadline,
    }


def _sample_generated_architectures(args: argparse.Namespace, output: Path, count: int):
    from archai_benchmark.learned_search import NB201_OPS
    from archai_benchmark.nasbench201 import architecture_from_string
    from archai_core.schema import TensorSpec
    from archai_generator.model import GENERATABLE_OPS

    checkpoint = output / "generator.pt"
    if not checkpoint.is_file():
        return []
    model = load_generator_from_checkpoint(checkpoint)
    architectures = []
    vocab = tuple(model.config.vocabulary)
    input_spec = TensorSpec(channels=3, height=32, width=32)
    if vocab == NB201_OPS or "skip_connect" in vocab:
        for offset in range(count * 16):
            if len(architectures) >= count:
                break
            tokens_batch = model.sample_tokens(
                1,
                steps=6,
                seed=args.seed + 100 + offset,
                condition=(0.95, 0.5, 0, 0, 1, 0, 0, 0),
            )
            tokens = tokens_batch[0] if tokens_batch else []
            if len(tokens) != 6:
                continue
            encoding = (
                f"|{tokens[0]}~0|+|{tokens[1]}~0|{tokens[2]}~1|"
                f"+|{tokens[3]}~0|{tokens[4]}~1|{tokens[5]}~2|"
            )
            try:
                architectures.append(
                    architecture_from_string(encoding, input_spec=input_spec, output_classes=10)
                )
            except (TypeError, ValueError):
                continue
        return architectures
    if vocab != GENERATABLE_OPS:
        return []
    for offset in range(count):
        sampled = model.sample(
            seed=args.seed + 100 + offset,
            condition=(0.0,) * model.config.condition_dim,
            input_spec=input_spec,
            output_classes=10,
        )
        if sampled:
            architectures.append(sampled[-1])
    return architectures[:count]


def evaluate_on_cifar(args: argparse.Namespace, output: Path, deadline: float) -> dict:
    import torch
    from archai_core.validation import validate_architecture
    from archai_training.candidate import train_candidate
    from archai_training.engine import TrainingConfig
    from torch.utils.data import DataLoader, TensorDataset

    already: list[dict] = []
    prior_path = output / "cifar10_eval.json"
    if args.resume and prior_path.is_file():
        already = list(json.loads(prior_path.read_text()).get("candidates") or [])
    remaining = max(0, args.cifar_architectures - len(already))
    architectures = _sample_generated_architectures(args, output, args.cifar_architectures)
    architectures = architectures[len(already) : len(already) + remaining]
    if not architectures and not already:
        return {"kind": "cifar10_eval", "skipped": True, "reason": "no generated candidates"}
    if args.smoke:
        generator = torch.Generator().manual_seed(args.seed)
        train_loader = DataLoader(
            TensorDataset(
                torch.randn((16, 3, 32, 32), generator=generator),
                torch.randint(0, 10, (16,), generator=generator),
            ),
            batch_size=4,
        )
        val_loader = DataLoader(
            TensorDataset(
                torch.randn((8, 3, 32, 32), generator=generator),
                torch.randint(0, 10, (8,), generator=generator),
            ),
            batch_size=4,
        )
        evidence = "synthetic_training"
        test_loader = None
    else:
        from archai_training.datasets import ImageDatasetConfig, build_image_datasets

        splits = build_image_datasets(
            ImageDatasetConfig(
                name="cifar10",
                root=str(output / "cifar10"),
                validation_fraction=0.1,
                download=True,
                seed=args.seed,
            )
        )
        train_loader = DataLoader(splits["train"], batch_size=128, shuffle=True)
        val_loader = DataLoader(splits["validation"], batch_size=128)
        test_loader = DataLoader(splits["test"], batch_size=128)
        evidence = "measured_training"
    device = device_of(args.device)
    reports = list(already)
    for index, architecture in enumerate(architectures, start=len(already)):
        if time.time() >= deadline:
            break
        validate_architecture(architecture)
        ckpt = output / f"candidate_{index}.pt"
        result = train_candidate(
            architecture,
            train_loader,
            val_loader,
            TrainingConfig(epochs=args.cifar_epochs, seed=args.seed + index, device=device),
            checkpoint_path=str(ckpt),
        )
        row = {
            "index": index,
            "architecture_hash": architecture.with_id().content_hash(),
            "epochs_completed": result.epochs_completed,
            "best_validation_loss": result.best_validation_loss,
            "wall_clock_seconds": result.wall_clock_seconds,
            "checkpoint_sha256": sha256_file(ckpt) if ckpt.is_file() else None,
            "evidence_type": evidence,
            "protocol": "archai_training.engine (Adam, this repo default); not official NATS-Bench 200-epoch SGD",
        }
        if test_loader is not None and ckpt.is_file():
            from archai_compiler.pytorch_compiler import compile_architecture

            compiled = compile_architecture(architecture)
            payload = torch.load(ckpt, map_location="cpu", weights_only=True)
            state = payload["state_dict"] if "state_dict" in payload else payload
            compiled.load_state_dict(state)
            compiled.to(device)
            compiled.eval()
            correct = total = 0
            with torch.no_grad():
                for inputs, targets in test_loader:
                    logits = compiled(inputs.to(device))
                    correct += int((logits.argmax(1).cpu() == targets).sum())
                    total += int(targets.shape[0])
            row["held_out_test_accuracy"] = correct / max(1, total)
            row["test_split"] = "cifar10 official test set, not used for selection"
        reports.append(row)
        write_json(prior_path, {"candidates": reports})
    return {
        "kind": "cifar10_eval",
        "candidates": reports,
        "requested": args.cifar_architectures,
        "completed": len(reports),
        "scale": "cpu_smoke" if args.smoke else "kaggle_gpu_planned",
        "stopped_for_time_budget": time.time() >= deadline,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/kaggle/working/archai_v1"))
    parser.add_argument("--table", type=Path, default=None)
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="extracted official NATS-Bench -simple directory (unused by --smoke)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="tiny CPU path: fixture table, few epochs, synthetic candidate training",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--time-budget-hours", type=float, default=9.0)
    parser.add_argument("--checkpoint-minutes", type=float, default=15)
    parser.add_argument("--generator-cells", type=int, default=DEFAULT_GENERATOR_CELLS)
    parser.add_argument("--generator-epochs", type=int, default=DEFAULT_GENERATOR_EPOCHS)
    parser.add_argument("--predictor-cells", type=int, default=DEFAULT_GENERATOR_CELLS)
    parser.add_argument("--predictor-epochs", type=int, default=DEFAULT_PREDICTOR_EPOCHS)
    parser.add_argument("--cifar-architectures", type=int, default=DEFAULT_CIFAR_ARCHITECTURES)
    parser.add_argument("--cifar-epochs", type=int, default=DEFAULT_CIFAR_EPOCHS)
    args = parser.parse_args(argv)
    if args.smoke:
        args.generator_cells = min(args.generator_cells, 8)
        args.generator_epochs = min(args.generator_epochs, 2)
        args.predictor_cells = min(args.predictor_cells, 16)
        args.predictor_epochs = min(args.predictor_epochs, 2)
        args.cifar_architectures = min(args.cifar_architectures, 1)
        args.cifar_epochs = min(args.cifar_epochs, 1)
        args.time_budget_hours = min(args.time_budget_hours, 0.25)
        args.checkpoint_minutes = min(args.checkpoint_minutes, 1)
        if args.output == Path("/kaggle/working/archai_v1"):
            args.output = Path("/tmp/archai_v1_smoke")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    deadline = started + args.time_budget_hours * 3600
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    table = find_table(args)
    metrics = {
        "started_unix": started,
        "smoke": args.smoke,
        "device": device_of(args.device),
        "time_budget_hours": args.time_budget_hours,
        "time_budget_note": None
        if args.smoke
        else (
            "Nine hours is a plan that fits a 12-hour Kaggle GPU session; actual wall time "
            "is recorded in wall_clock_seconds at the end of the run."
        ),
        "table": str(table),
        "table_sha256": sha256_file(table),
        "seed": args.seed,
    }
    write_json(output / "metrics.json", metrics)
    metrics["generator"] = train_generator(args, table, output, deadline)
    write_json(output / "metrics.json", metrics)
    metrics["predictor"] = train_predictor(args, table, output, deadline)
    write_json(output / "metrics.json", metrics)
    metrics["cifar10_eval"] = evaluate_on_cifar(args, output, deadline)
    metrics["wall_clock_seconds"] = time.time() - started
    metrics["finished_unix"] = time.time()
    write_json(output / "metrics.json", metrics)
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "metrics_sha256": sha256_file(output / "metrics.json"),
                "smoke": args.smoke,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
