"""Train/evaluate the ArchAI predictor on a real NATS-Bench archive.

This command intentionally requires an explicit archive path and index list. It
never downloads data, invents labels, or uses the test split for selection.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from archai_benchmark.adapter import NATSBenchAdapter
from archai_benchmark.integrity import sha256_file
from archai_benchmark.nasbench201 import architecture_from_string
from archai_core.schema import TensorSpec
from archai_predictor.data import ArchitectureRecord, split_records
from archai_predictor.model import PerformancePredictor, PredictorConfig
from archai_predictor.training import evaluate_predictor, fit_predictor, save_checkpoint


def _code_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "working-tree"


def collect_records(adapter: NATSBenchAdapter, indices: list[int], seed: int, dataset: str) -> list[ArchitectureRecord]:
    records = []
    for index in indices:
        benchmark = adapter.query(index, seed=seed)
        if benchmark.architecture_string is None:
            raise RuntimeError(f"benchmark did not return architecture string for index {index}")
        architecture = architecture_from_string(benchmark.architecture_string,
            input_spec=TensorSpec(channels=3, height=32, width=32), output_classes=10)
        # NATS-Bench reports accuracy in percentage points; convert once and
        # preserve the source in the record instead of mixing units.
        records.append(ArchitectureRecord(architecture, benchmark.validation_accuracy / 100.0,
                                          task_features=(1.0 if dataset == "cifar10" else 0.0,) + (0.0,) * 7,
                                          source="NATS-Bench"))
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-path", required=True)
    parser.add_argument("--benchmark-sha256", required=True)
    parser.add_argument("--indices", required=True, help="comma-separated architecture indices")
    parser.add_argument("--dataset", default="cifar10")
    parser.add_argument("--search-space", default="tss")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    indices = [int(value.strip()) for value in args.indices.split(",") if value.strip()]
    if len(indices) < 3:
        parser.error("at least three architecture indices are required for train/validation/test")
    actual_checksum = sha256_file(args.benchmark_path)
    if actual_checksum != args.benchmark_sha256.lower():
        parser.error("benchmark archive checksum mismatch")
    adapter = NATSBenchAdapter(args.benchmark_path, args.search_space, args.dataset).open()
    records = collect_records(adapter, indices, args.seed, args.dataset)
    splits = split_records(records, seed=args.seed)
    if not splits["train"] or not splits["validation"] or not splits["test"]:
        parser.error("indices must produce non-empty train, validation, and test partitions")
    model = PerformancePredictor(PredictorConfig())
    history = fit_predictor(model, splits["train"], epochs=args.epochs, seed=args.seed,
                            batch_size=args.batch_size)
    validation = evaluate_predictor(model, splits["validation"])
    test = evaluate_predictor(model, splits["test"])
    metadata = {"model": "ArchAI-Predictor", "dataset": args.dataset, "search_space": args.search_space,
                "seed": args.seed, "code_revision": _code_revision(),
                "architecture_ids": [record.architecture.content_hash() for record in records],
                "split_sizes": {key: len(value) for key, value in splits.items()},
                "test_used_for_selection": False, "archive_sha256": actual_checksum}
    save_checkpoint(model, args.checkpoint, metadata)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"metadata": metadata, "training_loss": history,
                                       "validation": validation, "test": test}, indent=2, sort_keys=True))
    print(json.dumps({"checkpoint": str(args.checkpoint), "report": str(args.report), "validation": validation, "test": test}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
