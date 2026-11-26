"""Tabulate every NATS-Bench TSS cell once (benchmark lookups, no training).

The table is for reporting (oracle regret) and as offline training data for the
ArchAI-V1 predictor/generator. Search policies never read it. Each chunk runs in a
fresh process to keep memory bounded, and rows are written as JSONL outside git.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from archai_benchmark.adapter import NATSBenchAdapter
from archai_benchmark.integrity import sha256_path


def tabulate(path: str, start: int, stop: int, seeds: tuple[int, ...], dataset: str) -> list[dict]:
    adapter = NATSBenchAdapter(path, "tss", dataset).open()
    rows = []
    for index in range(start, stop):
        trials = []
        for seed in seeds:
            record = adapter.query(index, seed=seed)
            trials.append({"seed": seed, "trial_seed": record.benchmark_trial_seed,
                           "validation_accuracy": record.validation_accuracy,
                           "test_accuracy": record.test_accuracy})
        cost = adapter.cost(index)
        rows.append({"index": index, "architecture_string": adapter.architecture_string(index),
                     "trials": trials, **cost})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-path", required=True)
    parser.add_argument("--benchmark-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True, help="JSONL output (keep outside git)")
    parser.add_argument("--dataset", default="cifar10")
    parser.add_argument("--seeds", default="0,1,2", help="reproducibility seeds mapped onto archive trial seeds")
    parser.add_argument("--chunk", type=int, default=1000)
    parser.add_argument("--stop", type=int, default=15625)
    parser.add_argument("--worker", nargs=2, type=int, metavar=("START", "STOP"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(","))
    if args.worker:
        for row in tabulate(args.benchmark_path, args.worker[0], args.worker[1], seeds, args.dataset):
            print(json.dumps(row, sort_keys=True))
        return 0
    if sha256_path(args.benchmark_path) != args.benchmark_sha256.lower():
        parser.error("benchmark archive checksum mismatch")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    if args.output.exists():
        done = sum(1 for line in args.output.read_text().splitlines() if line.strip())
    with args.output.open("a") as handle:
        for start in range(done, args.stop, args.chunk):
            stop = min(start + args.chunk, args.stop)
            result = subprocess.run([sys.executable, __file__, "--benchmark-path", args.benchmark_path,
                                     "--benchmark-sha256", args.benchmark_sha256, "--output", str(args.output),
                                     "--dataset", args.dataset, "--seeds", args.seeds,
                                     "--worker", str(start), str(stop)],
                                    check=True, capture_output=True, text=True)
            handle.write(result.stdout)
            handle.flush()
            print(json.dumps({"tabulated": stop}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
