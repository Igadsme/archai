"""Render a measured matrix report as Markdown, adding regret against the full-space oracle.

Inputs: runs.json (run_experiment_matrix), report.json (scripts/build_report.py), and the
benchmark table (scripts/benchmark_table.py). The oracle is the best cifar10-valid validation
accuracy in the whole space for the archive trial each run used; it is reported for context
and never given to a policy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai_benchmark.research_metrics import summarize_seeds


def oracle_by_seed(table_path: Path, seeds: list[int]) -> dict[int, dict]:
    best: dict[int, dict] = {}
    for line in table_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        available = list(dict.fromkeys(trial["trial_seed"] for trial in row["trials"]))
        by_trial = {trial["trial_seed"]: trial for trial in row["trials"]}
        for seed in seeds:
            trial = by_trial[available[seed % len(available)]]
            if seed not in best or trial["validation_accuracy"] > best[seed]["validation_accuracy"]:
                best[seed] = {"index": row["index"], **trial}
    return best


def load_cells(table_path: Path) -> dict[int, dict]:
    cells = {}
    for line in table_path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            cells[row["index"]] = row
    return cells


def validation_for(row: dict, seed: int) -> float:
    available = list(dict.fromkeys(trial["trial_seed"] for trial in row["trials"]))
    by_trial = {trial["trial_seed"]: trial for trial in row["trials"]}
    return by_trial[available[seed % len(available)]]["validation_accuracy"]


def front(points: list[dict]) -> list[dict]:
    """Non-dominated points: maximize validation accuracy, minimize params."""
    ordered = sorted(points, key=lambda item: (item["params_m"], -item["validation_accuracy"]))
    result, best = [], float("-inf")
    for item in ordered:
        if item["validation_accuracy"] > best:
            result.append(item)
            best = item["validation_accuracy"]
    return result


def pareto_payload(runs: list[dict], cells: dict[int, dict]) -> dict:
    policies: dict[str, dict] = {}
    for run in runs:
        seed = int(run["seed"])
        points = [{"index": index, "architecture_string": cells[index]["architecture_string"],
                   "validation_accuracy": validation_for(cells[index], seed), "params_m": cells[index]["params_m"],
                   "flops_m": cells[index]["flops_m"]} for index in run["evaluated_indices"]]
        policies.setdefault(run["algorithm"], {})[str(seed)] = {
            "front": front(points), "hypervolume": run.get("hypervolume_validation_params")}
    space = [{"index": index, "architecture_string": row["architecture_string"],
              "validation_accuracy": validation_for(row, 0), "params_m": row["params_m"], "flops_m": row["flops_m"]}
             for index, row in cells.items()]
    return {"objectives": {"maximize": "validation_accuracy (cifar10-valid, %)", "minimize": "params_m (millions)"},
            "evidence_type": "benchmark_lookup", "hypervolume_reference": [0.0, 1.6],
            "full_space_front_trial_seed_for_seed0": front(space), "policies": policies}


def fmt(summary: dict, digits: int = 2) -> str:
    return f"{summary['mean']:.{digits}f} [{summary['ci_low']:.{digits}f}, {summary['ci_high']:.{digits}f}]"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args()
    runs = json.loads(args.runs.read_text())
    report = json.loads(args.report.read_text())
    seeds = sorted({int(run["seed"]) for run in runs})
    oracle = oracle_by_seed(args.table, seeds)
    rows, regrets = [], {}
    for name, summary in report["algorithms"].items():
        algorithm_runs = [run for run in runs if run["algorithm"] == name]
        regret = summarize_seeds([oracle[int(run["seed"])]["validation_accuracy"] - run["best_validation_accuracy"]
                                  for run in algorithm_runs], seed=args.bootstrap_seed)
        wall = sum(run.get("wall_clock_seconds", 0.0) for run in algorithm_runs)
        ablation = any(run.get("ablation") for run in algorithm_runs)
        regrets[name] = regret
        rows.append((name, ablation, summary, regret, wall))
    rows.sort(key=lambda row: (row[1], -row[2]["best_validation_accuracy"]["mean"]))
    lines = ["| Policy | Ablation | Runs | Best validation acc. | Test acc. of selected cell | Regret vs. oracle (val.) | Hypervolume (val. × params) | Wall clock (s, all seeds) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, ablation, summary, regret, wall in rows:
        hv = summary.get("hypervolume_validation_params")
        lines.append(f"| {name} | {'yes' if ablation else 'no'} | {summary['runs']} | {fmt(summary['best_validation_accuracy'])} | "
                     f"{fmt(summary['final_test_accuracy'])} | {fmt(regret, 3)} | {fmt(hv) if hv else 'n/a'} | {wall:.0f} |")
    oracle_lines = ["| Seed | Oracle cell | Oracle validation acc. | Its test acc. | Archive trial |", "| --- | --- | --- | --- | --- |"]
    for seed in seeds:
        item = oracle[seed]
        oracle_lines.append(f"| {seed} | {item['index']} | {item['validation_accuracy']:.3f} | {item['test_accuracy']:.2f} | {item['trial_seed']} |")
    text = "\n".join(["Values are means over seeds with 95% bootstrap CIs [low, high]. Evidence type: benchmark_lookup.", "",
                      *lines, "", "Full-space oracle per seed (context only, never visible to any policy):", "", *oracle_lines, ""])
    args.output.write_text(text)
    pareto = pareto_payload(runs, load_cells(args.table))
    (args.output.parent / "pareto.json").write_text(json.dumps(pareto, sort_keys=True))
    args.output.with_suffix(".regret.json").write_text(json.dumps(regrets, indent=2, sort_keys=True))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
