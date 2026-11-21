from __future__ import annotations

from collections import defaultdict

from .research_metrics import summarize_seeds


def validate_run_records(records: list[dict]) -> None:
    for record in records:
        if record.get("selected_on") == "test" or record.get("test_used_for_selection") is True:
            raise ValueError(f"test leakage detected for run {record.get('run_id', '<unknown>')}")
        for required in ("algorithm", "seed", "best_validation_accuracy"):
            if required not in record:
                raise ValueError(f"run is missing required field: {required}")


def build_research_report(records: list[dict], *, seed: int = 0) -> dict:
    validate_run_records(records)
    grouped = defaultdict(list)
    for record in records:
        grouped[str(record["algorithm"])].append(record)
    algorithms = {}
    for algorithm, runs in sorted(grouped.items()):
        summary = {"best_validation_accuracy": summarize_seeds([float(run["best_validation_accuracy"]) for run in runs], seed=seed)}
        if all("final_test_accuracy" in run for run in runs):
            summary["final_test_accuracy"] = summarize_seeds([float(run["final_test_accuracy"]) for run in runs], seed=seed)
        if all("search_cost" in run for run in runs):
            summary["search_cost"] = summarize_seeds([float(run["search_cost"]) for run in runs], seed=seed)
        summary["runs"] = len(runs)
        algorithms[algorithm] = summary
    return {"run_count": len(records), "algorithms": algorithms, "test_selection_policy": "validation_only"}
