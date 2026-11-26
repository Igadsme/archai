import pytest
from archai_benchmark.reporting import build_research_report


def test_report_groups_seeds_and_keeps_test_separate():
    report = build_research_report([
        {"run_id": "r1", "algorithm": "random", "seed": 1, "best_validation_accuracy": 0.8, "final_test_accuracy": 0.79, "search_cost": 10, "selected_on": "validation"},
        {"run_id": "r2", "algorithm": "random", "seed": 2, "best_validation_accuracy": 0.82, "final_test_accuracy": 0.81, "search_cost": 12, "selected_on": "validation"},
    ])
    assert report["test_selection_policy"] == "validation_only"
    assert report["algorithms"]["random"]["runs"] == 2


def test_report_rejects_test_selection():
    with pytest.raises(ValueError, match="test leakage"):
        build_research_report([{"run_id": "bad", "algorithm": "random", "seed": 1,
                               "best_validation_accuracy": 0.8, "selected_on": "test"}])


def test_report_rejects_duplicate_seeds_and_mismatched_budgets():
    base = {"algorithm": "random", "seed": 1, "best_validation_accuracy": 0.8,
            "selected_on": "validation", "budget": 10}
    with pytest.raises(ValueError, match="duplicate algorithm/seed"):
        build_research_report([base, dict(base)])
    with pytest.raises(ValueError, match="matched-budget"):
        build_research_report([base, {**base, "algorithm": "evolution", "seed": 2, "budget": 20}])


def test_report_can_require_matched_baselines_and_repeated_seeds():
    records = [
        {"algorithm": algorithm, "seed": seed, "best_validation_accuracy": 0.8,
         "selected_on": "validation", "budget": 10}
        for algorithm in ("random", "evolution") for seed in (1, 2)
    ]
    report = build_research_report(records, required_algorithms=("random", "evolution"), min_seeds=2)
    assert report["required_algorithms"] == ["random", "evolution"]
    assert report["minimum_seeds"] == 2
    with pytest.raises(ValueError, match="required algorithms"):
        build_research_report(records[:2], required_algorithms=("random", "evolution"), min_seeds=1)
