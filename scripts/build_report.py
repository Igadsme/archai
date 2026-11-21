"""Build a research summary from JSON run records without test leakage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai_benchmark.reporting import build_research_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True, help="JSON array of run records")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--require-algorithm", action="append", default=[])
    parser.add_argument("--min-seeds", type=int, default=1)
    args = parser.parse_args()
    records = json.loads(args.runs.read_text())
    report = build_research_report(records, seed=args.seed,
                                   required_algorithms=tuple(args.require_algorithm),
                                   min_seeds=args.min_seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
