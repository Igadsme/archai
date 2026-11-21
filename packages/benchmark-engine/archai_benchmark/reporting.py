from __future__ import annotations

from collections import defaultdict

from .research_metrics import summarize_seeds


def validate_run_records(records: list[dict]) -> None:
    identities = set()
    declared_budgets = set()
    for record in records:
        if record.get("selected_on") == "test" or record.get("test_used_for_selection") is True:
            raise ValueError(f"test leakage detected for run {record.get('run_id', '<unknown>')}")
        for required in ("algorithm", "seed", "best_validation_accuracy"):
            if required not in record:
                raise ValueError(f"run is missing required field: {required}")
        identity = (str(record["algorithm"]), int(record["seed"]))
        if identity in identities:
            raise ValueError(f"duplicate algorithm/seed run: {identity[0]}/{identity[1]}")
        identities.add(identity)
        if "budget" in record:
            declared_budgets.add(float(record["budget"]))
    if len(declared_budgets) > 1:
        raise ValueError("matched-budget comparison requires one declared budget")


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
    budget = next(iter({float(record["budget"]) for record in records if "budget" in record}), None)
    report = {"run_count": len(records), "algorithms": algorithms,
              "test_selection_policy": "validation_only"}
    if budget is not None:
        report["matched_budget"] = budget
    return report
