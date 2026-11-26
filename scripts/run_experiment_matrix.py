"""Run a matched-budget experiment matrix (algorithms x seeds) and build its research report."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from archai_benchmark import NATSBenchAdapter, build_research_report
from archai_benchmark.integrity import sha256_path

try:
    from scripts.run_benchmark_search import ALGORITHMS, run_search
except ModuleNotFoundError:  # executed as `python scripts/run_experiment_matrix.py`
    from run_benchmark_search import ALGORITHMS, run_search

REQUIRED_KEYS = ("name", "benchmark", "indices", "budget", "seeds", "algorithms")


def resolve_variants(config: dict) -> list[dict]:
    """Expand `algorithms` (+ optional `ablations`) into named policy variants.

    A plain string such as "bayesian" uses the per-algorithm defaults from the config
    section of the same name; an object `{"name", "algorithm", "params"}` overrides them.
    Ablations use the same object form and are reported as separate named variants.
    """
    variants = []
    entries = list(config["algorithms"]) + list(config.get("ablations", []))
    for entry in entries:
        if isinstance(entry, str):
            entry = {"name": entry, "algorithm": entry}
        if not isinstance(entry, dict) or "algorithm" not in entry:
            raise ValueError(f"invalid algorithm entry: {entry!r}")
        algorithm = str(entry["algorithm"])
        if algorithm not in ALGORITHMS:
            raise ValueError(f"algorithms must use values from {ALGORITHMS}; got {algorithm!r}")
        params = {**dict(config.get(algorithm, {})), **dict(entry.get("params", {}))}
        variants.append({"name": str(entry.get("name", algorithm)), "algorithm": algorithm,
                         "params": params, "ablation": entry in config.get("ablations", [])})
    names = [variant["name"] for variant in variants]
    if not variants or len(set(names)) != len(names):
        raise ValueError(f"algorithm variant names must be unique and non-empty; got {names}")
    return variants


def load_matrix(path: str | Path) -> dict:
    config = json.loads(Path(path).read_text())
    missing = [key for key in REQUIRED_KEYS if key not in config]
    if missing:
        raise ValueError(f"experiment config is missing: {', '.join(missing)}")
    if int(config["budget"]) <= 0:
        raise ValueError("budget must be positive")
    seeds = [int(seed) for seed in config["seeds"]]
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be a non-empty list of unique integers")
    config["variants"] = resolve_variants(config)
    config["indices"] = resolve_indices(config["indices"])
    if len(config["indices"]) < 2:
        raise ValueError("index pool must contain at least two architectures")
    return config


def resolve_indices(spec) -> list[int]:
    if isinstance(spec, dict):
        start, stop = int(spec["start"]), int(spec["stop"])
        if start < 0 or stop <= start:
            raise ValueError("index range must satisfy 0 <= start < stop")
        return list(range(start, stop))
    values = [int(value) for value in spec]
    if len(set(values)) != len(values) or any(value < 0 for value in values):
        raise ValueError("explicit indices must be unique and non-negative")
    return values


def planned_runs(config: dict) -> list[dict]:
    return [{"run_id": f"{config['name']}/{variant['name']}/seed{seed}", "algorithm": variant["name"],
             "base_algorithm": variant["algorithm"], "params": variant["params"],
             "ablation": variant["ablation"], "seed": int(seed), "budget": int(config["budget"])}
            for variant in config["variants"] for seed in config["seeds"]]


def to_run_record(report: dict, plan: dict) -> dict:
    """Map a run_benchmark_search report onto build_research_report's record schema."""
    return {"run_id": plan["run_id"], "algorithm": plan["algorithm"],
            "base_algorithm": plan["base_algorithm"], "policy_params": report["policy_params"],
            "ablation": plan["ablation"], "seed": report["seed"],
            "budget": report["budget"], "selected_on": "validation",
            "test_used_for_selection": False,
            "best_validation_accuracy": report["selected_validation_accuracy"],
            "final_test_accuracy": report["held_out_test_accuracy"],
            "search_cost": report["queries"], "selected_index": report["selected_index"],
            "evidence_type": report["evidence_type"],
            "validation_trace": report["validation_trace"]}


def run_matrix(config: dict, adapter, output: Path, *, archive_sha256: str | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for plan in planned_runs(config):
        cache = output / "cache" / f"{plan['algorithm']}-seed{plan['seed']}.sqlite"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.unlink(missing_ok=True)  # fresh cache per run keeps query budgets matched
        started = time.monotonic()
        report = run_search(adapter, config["indices"], budget=plan["budget"],
                            algorithm=plan["base_algorithm"], seed=plan["seed"], cache_path=cache,
                            params=plan["params"])
        record = to_run_record(report, plan)
        record["wall_clock_seconds"] = round(time.monotonic() - started, 3)
        if archive_sha256:
            record["archive_sha256"] = archive_sha256
        records.append(record)
    (output / "runs.json").write_text(json.dumps(records, indent=2, sort_keys=True))
    report = build_research_report(records,
                                   seed=int(config.get("report", {}).get("bootstrap_seed", 0)),
                                   required_algorithms=tuple(v["name"] for v in config["variants"]),
                                   min_seeds=len(config["seeds"]))
    report.update({"experiment": config["name"], "benchmark": config["benchmark"],
                   "index_pool_size": len(config["indices"]), "evidence_type": "benchmark_lookup",
                   "variants": config["variants"], "seeds": config["seeds"],
                   "ablations": [v["name"] for v in config["variants"] if v["ablation"]]})
    if archive_sha256:
        report["archive_sha256"] = archive_sha256
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--benchmark-path")
    parser.add_argument("--benchmark-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="print planned runs only")
    args = parser.parse_args()
    try:
        config = load_matrix(args.config)
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps({"experiment": config["name"], "index_pool_size": len(config["indices"]),
                          "runs": planned_runs(config)}, sort_keys=True))
        return 0
    if not (args.benchmark_path and args.benchmark_sha256 and args.output):
        parser.error("--benchmark-path, --benchmark-sha256 and --output are required unless --dry-run")
    actual = sha256_path(args.benchmark_path)
    if actual != args.benchmark_sha256.lower():
        parser.error("benchmark archive checksum mismatch")
    benchmark = config["benchmark"]
    adapter = NATSBenchAdapter(args.benchmark_path, benchmark.get("search_space", "tss"),
                               benchmark.get("dataset", "cifar10")).open()
    report = run_matrix(config, adapter, args.output, archive_sha256=actual)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
